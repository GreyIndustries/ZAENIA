"""Fixed Blender worker. Only JSON data comes from the assistant; never code."""
import bpy
import json
import sys
from pathlib import Path

job=json.loads(Path(sys.argv[sys.argv.index('--')+1]).read_text(encoding='utf-8'))
if job.get('output'):
    obj=bpy.data.objects.get(job['objectName'])
    if obj is None: raise ValueError('The named object is not in the scene.')
    obj.location=job['location']
    bpy.context.preferences.filepaths.save_version=0
    bpy.ops.wm.save_as_mainfile(filepath=job['output'],check_existing=False)
objects=[{'name':obj.name,'type':obj.type,'location':list(obj.location)} for obj in list(bpy.data.objects)[:1000]]
Path(job['receipt']).write_text(json.dumps({'objects':objects}),encoding='utf-8')
