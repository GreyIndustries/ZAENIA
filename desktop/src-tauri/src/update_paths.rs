use std::path::{Path, PathBuf};

fn valid_id(id: &str) -> bool {
    !id.is_empty() && id.len() <= 64
        && id.chars().next().map_or(false, |c| c.is_ascii_alphanumeric())
        && id.chars().all(|c| c.is_ascii_alphanumeric() || c == '.' || c == '-')
}

fn has_update(root: &Path, id: &str) -> bool {
    root.join("core").join("api").join("server.py").is_file()
        && root.join("scripts").join("install_update.ps1").is_file()
        && root.join("updates").join("pending").join(id).join("manifest.json").is_file()
}

/// Only trusted process configuration/build ancestors are searched, never client-supplied paths.
pub fn find_update_root(build_root: &Path, configured: Option<&Path>, id: &str) -> Result<PathBuf, String> {
    if !valid_id(id) { return Err("Choose a valid update from Settings > Updates.".into()); }
    if let Some(root) = configured {
        if !root.is_absolute() || !has_update(root, id) {
            return Err("ZAENIA_PROJECT_ROOT does not contain this staged update and the project installer. Check that Windows setting or refresh Updates.".into());
        }
        return Ok(root.to_path_buf());
    }
    // A build made in <project>/.tmp/<build>/ must use the deployment project,
    // not its temporary build copy. Search outer roots before inner snapshots.
    let ancestors: Vec<_> = build_root.ancestors().collect();
    for root in ancestors.into_iter().rev() {
        if has_update(root, id) { return Ok(root.to_path_buf()); }
    }
    Err("This staged update could not be found in the ZAE project. Refresh Updates or set ZAENIA_PROJECT_ROOT on this PC.".into())
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::{fs, sync::atomic::{AtomicU64, Ordering}};
    static NEXT: AtomicU64 = AtomicU64::new(0);
    const ID: &str = "system-0.31.1-test";
    fn fixture() -> PathBuf {
        let root = std::env::temp_dir().join(format!("zaenia-update-root-test-{}-{}", std::process::id(), NEXT.fetch_add(1, Ordering::Relaxed)));
        fs::create_dir_all(&root).unwrap(); root
    }
    fn project(root: &Path, staged: bool) {
        fs::create_dir_all(root.join("core/api")).unwrap();
        fs::create_dir_all(root.join("scripts")).unwrap();
        fs::write(root.join("core/api/server.py"), "# fixture").unwrap();
        fs::write(root.join("scripts/install_update.ps1"), "# fixture").unwrap();
        if staged {
            fs::create_dir_all(root.join("updates/pending").join(ID)).unwrap();
            fs::write(root.join("updates/pending").join(ID).join("manifest.json"), "{}").unwrap();
        }
    }
    #[test] fn temporary_build_uses_deployment_project_even_if_snapshot_contains_same_id() {
        let root=fixture(); project(&root,true); let build=root.join(".tmp/build");project(&build,true);
        assert_eq!(find_update_root(&build,None,ID).unwrap(),root);
    }
    #[test] fn direct_checkout_build_still_works() {
        let root=fixture();project(&root,true);assert_eq!(find_update_root(&root,None,ID).unwrap(),root);
    }
    #[test] fn validated_owner_configuration_can_select_a_separate_deployment_root() {
        let root=fixture();let deploy=root.join("deploy");project(&deploy,true);
        assert_eq!(find_update_root(&root.join("other"),Some(&deploy),ID).unwrap(),deploy);
    }
    #[test] fn wrong_configuration_and_missing_updates_fail_without_launching_anything() {
        let root=fixture();project(&root,false);
        assert!(find_update_root(&root,Some(&root),ID).is_err());
        assert!(find_update_root(&root,Some(Path::new("relative")),ID).is_err());
        assert!(find_update_root(&root,None,ID).is_err());
    }
    #[test] fn traversal_and_shell_metacharacters_are_not_update_ids() {
        let root=fixture();project(&root,true);
        for id in ["../escape", "a\\b", "a;start", "", "-option", "."] { assert!(find_update_root(&root,None,id).is_err()); }
    }
    #[test] fn manifests_without_installer_and_core_markers_are_not_projects() {
        let root=fixture();fs::create_dir_all(root.join("updates/pending").join(ID)).unwrap();
        fs::write(root.join("updates/pending").join(ID).join("manifest.json"),"{}").unwrap();
        assert!(find_update_root(&root,None,ID).is_err());
    }
}


/// Runtime configuration is trusted process/account configuration, never a client or model path.
pub fn runtime_root(configured: Option<&Path>, config_files: &[PathBuf], fallback: &Path) -> Result<PathBuf, String> {
    let validate = |root: &Path| -> Result<PathBuf, String> {
        if !root.is_absolute() || root.components().any(|c| c.as_os_str().to_string_lossy().eq_ignore_ascii_case(".tmp"))
            || !root.join("core/api/update_routes.py").is_file() || !root.join("desktop").is_dir()
            || !root.join("scripts/install_update.ps1").is_file() {
            return Err("Choose the real ZAENIA deployment folder, not a temporary build. Check ZAENIA_PROJECT_ROOT/root.json.".into());
        }
        root.canonicalize().map_err(|_| "Could not resolve the deployment folder.".into())
    };
    if let Some(root) = configured { return validate(root); }
    for file in config_files {
        if file.is_file() {
            let text = std::fs::read_to_string(file).map_err(|_| "Could not read root.json.")?;
            // JSON is parsed by the app; this helper receives a plain path file only in unit tests.
            return validate(Path::new(text.trim()));
        }
    }
    validate(fallback)
}

#[cfg(test)] mod runtime_tests {
    use super::*;
    #[test] fn runtime_root_rejects_temporary_or_unvalidated_configuration() {
        assert!(runtime_root(Some(Path::new("relative")), &[], Path::new("missing")).is_err());
        assert!(runtime_root(Some(Path::new("C:/Projects/ZAENIA/.tmp/build")), &[], Path::new("missing")).is_err());
    }
    #[test] fn configured_root_is_validated_at_runtime() {
        let root=std::env::temp_dir().join(format!("zae-root-runtime-{}",std::process::id()));
        std::fs::create_dir_all(root.join("core/api")).unwrap();std::fs::create_dir_all(root.join("desktop")).unwrap();std::fs::create_dir_all(root.join("scripts")).unwrap();
        std::fs::write(root.join("core/api/update_routes.py"), "# test").unwrap();std::fs::write(root.join("scripts/install_update.ps1"), "# test").unwrap();
        assert_eq!(runtime_root(Some(&root), &[], Path::new("missing")).unwrap(),root.canonicalize().unwrap());
    }
}
