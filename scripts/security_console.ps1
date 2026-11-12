param(
  [Parameter(Mandatory=$true)][ValidateSet('unlock_passkey','unlock_voice','token_rotate','token_revoke','pair_desktop','phrase_setup','phrase_reset','mic_change','mic_reset','phone_voice_on','phone_voice_off','calm_password_setup','calm_password_reset')][string]$Mode,
  [ValidatePattern('^([0-9a-f]{32})?$')][string]$Request = ''
)
# Owner console for the Security tab. The passkey and the spoken phrase are only
# ever entered here, never in the app. Keep this file ASCII only.
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$projectPython = Join-Path $projectRoot '.venv\Scripts\python.exe'
Set-Location -LiteralPath $projectRoot
$Host.UI.RawUI.WindowTitle = 'ZAENIA - Security'

# Python is called directly (never inside a function or pipe) so passkey prompts and printed tokens show normally.

switch ($Mode) {
  'unlock_passkey' {
    if (-not $Request) { Write-Host 'Start again from the Security tab.'; break }
    Write-Host 'Unlock the Security tab with your passkey.'
    & $projectPython @('-m','core.api.security_unlock','passkey',$Request)
  }
  'unlock_voice' {
    if (-not $Request) { Write-Host 'Start again from the Security tab.'; break }
    Write-Host 'Unlock the Security tab with your spoken phrase. Your voice is checked too.'
    Write-Host 'Keep SteelSeries GG (Sonar) running. Loading the voice check...'
    & $projectPython @('-m','core.api.security_unlock','voice',$Request)
  }
  'token_rotate' {
    Write-Host 'Rotate the API token. The phone must reconnect with the new token afterwards.'
    & $projectPython @('-m','core.api.auth','rotate')
  }
  'token_revoke' {
    Write-Host 'Revoke the API token. Every phone and client signed in with it stops working.'
    if ((Read-Host 'Type REVOKE to continue') -eq 'REVOKE') { & $projectPython @('-m','core.api.auth','revoke') } else { Write-Host 'Nothing changed.' }
  }
  'pair_desktop' {
    Write-Host 'Re-pair this desktop app with a new approval key.'
    & $projectPython @('-m','core.api.server','pair-desktop')
  }
  'phrase_setup' {
    Write-Host 'Set up your spoken security phrase. You will say it twice.'
    & $projectPython @('-m','core.foundation.foundation_main','setup-voice-phrase')
  }
  'phrase_reset' {
    Write-Host 'Remove your spoken security phrase. You can set up a new one afterwards.'
    & $projectPython @('-m','core.foundation.foundation_main','reset-voice-phrase')
  }
  'mic_change' {
    Write-Host 'Choose the approved microphone. First, your passkey to list the microphones.'
    & $projectPython @('-m','core.foundation.foundation_main','list-mics')
    if ($LASTEXITCODE -eq 0) {
      $index = Read-Host 'Type the index of the microphone to approve (blank to cancel)'
      if ($index -match '^\d+$') { & $projectPython @('-m','core.foundation.foundation_main','set-mic',$index) } else { Write-Host 'Nothing changed.' }
    }
  }
  'mic_reset' {
    Write-Host 'Remove the approved microphone. Voice checks stop until you choose one again.'
    & $projectPython @('-m','core.foundation.foundation_main','reset-approved-mic')
  }
  'phone_voice_on' {
    Write-Host 'Turn on phone voice sign-in (also used to check your voice when you unlock the Security tab).'
    & $projectPython @('-m','core.api.mobile_voice_profile','enable')
  }
  'phone_voice_off' {
    Write-Host 'Turn off phone voice sign-in. Phones signed in by voice are signed out.'
    & $projectPython @('-m','core.api.mobile_voice_profile','disable')
  }
  'calm_password_setup' {
    Write-Host 'Create or change the separate Calm-view dashboard password. Your owner passkey approves this change.'
    & $projectPython @('-m','core.api.calm_password','setup')
  }
  'calm_password_reset' {
    Write-Host 'Reset only the Calm-view dashboard password. Your owner passkey approves this change.'
    & $projectPython @('-m','core.api.calm_password','reset')
  }
}
Read-Host 'Press Enter to close this window'
