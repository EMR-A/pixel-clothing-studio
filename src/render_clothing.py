# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Pixel Clothing Studio contributors
"""Render original installed GTA freemode clothing through Blender + Sollumz.

Run with Blender: --background --python render-clothing.py -- --plan render-plan.json --out OUTPUT --scratch SCRATCH
Does not modify game files. Filenames use source collection + local drawable + texture index.
"""
import argparse,json,math,sys,time,traceback,re,os,warnings,subprocess
warnings.filterwarnings('ignore',category=DeprecationWarning)
from pathlib import Path
import bpy,addon_utils,bmesh
import numpy as np
from mathutils import Vector,Matrix

tool_root=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(tool_root/'engine'/'dependencies'))
sys.path.insert(0,str(tool_root/'engine'/'addons'))
if os.environ.get('PIXEL_PYMATERIA_PATH'):sys.path.insert(0,os.environ['PIXEL_PYMATERIA_PATH'])
# Only dependencies licensed for redistribution are bundled. PyMateria is installed
# by the customer from its official distribution after reading its agreement.
addon=addon_utils.enable('sollumz',default_set=True,persistent=False)
if addon is None or not hasattr(bpy.types.Object,'sollum_type'):raise RuntimeError('Sollumz could not initialize. Check its dependencies.')

from szio import VPath
from szio.gta5 import try_load_asset,ShaderManager

ap=argparse.ArgumentParser()
ap.add_argument('--plan',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);ap.add_argument('--scratch',type=Path,required=True)
ap.add_argument('--max-variants',type=int,default=0);ap.add_argument('--start-job',type=int,default=0);ap.add_argument('--limit-jobs',type=int,default=0)
ap.add_argument('--only-keys',type=Path)
ap.add_argument('--engine',choices=['CYCLES','BLENDER_EEVEE'],default='CYCLES');ap.add_argument('--samples',type=int,default=24);ap.add_argument('--size',type=int,default=512)
ap.add_argument('--quality',type=int,default=100)
args=ap.parse_args(sys.argv[sys.argv.index('--')+1:]);plan=json.loads(args.plan.read_text(encoding='utf-8'))
args.out=args.out.resolve();args.scratch=args.scratch.resolve();args.out.mkdir(parents=True,exist_ok=True);args.scratch.mkdir(parents=True,exist_ok=True)
scene=bpy.context.scene
scene.render.engine=args.engine;scene.render.film_transparent=True;scene.render.resolution_x=args.size*2;scene.render.resolution_y=args.size*2;scene.render.resolution_percentage=100
scene.render.image_settings.file_format='PNG';scene.render.image_settings.color_mode='RGBA';scene.render.image_settings.color_depth='8';scene.render.image_settings.compression=20
scene.view_settings.view_transform='Standard';scene.view_settings.look='None';scene.view_settings.exposure=0;scene.view_settings.gamma=1
scene.render.use_persistent_data=True
if args.engine=='CYCLES':
    scene.cycles.samples=args.samples;scene.cycles.use_denoising=True
    prefs=bpy.context.preferences.addons['cycles'].preferences
    try:
        prefs.compute_device_type='OPTIX';prefs.get_devices()
        for d in prefs.devices:d.use=d.type=='OPTIX'
        scene.cycles.device='GPU' if any(d.use for d in prefs.devices) else 'CPU'
    except Exception:scene.cycles.device='CPU'

for obj in list(bpy.data.objects):bpy.data.objects.remove(obj,do_unlink=True)
camera_data=bpy.data.cameras.new('Catalog Camera');camera=bpy.data.objects.new('Catalog Camera',camera_data);scene.collection.objects.link(camera);scene.camera=camera;camera_data.type='ORTHO'
lights=[]
for name,pos,power,size in [('Key',(-3,-4,5),650,4),('Fill',(4,-2,3),350,4),('Rim',(1,4,4),500,3)]:
    light=bpy.data.lights.new(name,'AREA');light.energy=power;light.shape='DISK';light.size=size
    obj=bpy.data.objects.new(name,light);scene.collection.objects.link(obj);lights.append((obj,Vector(pos)))
world=bpy.data.worlds.new('Catalog World');world.use_nodes=True;world.node_tree.nodes['Background'].inputs['Color'].default_value=(.72,.72,.72,1);world.node_tree.nodes['Background'].inputs['Strength'].default_value=1;scene.world=world
studio_objects={camera.name,*[o.name for o,_ in lights]}

manifest=args.out/'manifest.jsonl';done={}
expected={f"{job['key']}/{texture.get('textureId',i) if texture else 0}" for job in plan['jobs'] for i,texture in enumerate(job['textures'] or [None])}
if manifest.exists():
    for line in manifest.read_text(encoding='utf-8').splitlines():
        try:
            row=json.loads(line)
            done.pop(row['key'],None)
            if row['key'] in expected and row.get('transparent') is True and row.get('lossless') is True and (row['status']=='empty' or (row['status']=='saved' and row.get('size')==args.size and row['path'].endswith('.webp') and (args.out/row['path']).is_file())):done[row['key']]=row
        except Exception:pass
state={'status':'running','build':plan['build'],'engine':args.engine,'size':args.size,'format':'webp','lossless':True,'transparent':True,'background':'transparent','angle':22,'totalJobs':len(plan['jobs']),'totalVariants':sum(len(j['textures']) or 1 for j in plan['jobs']),'saved':sum(r['status']=='saved' for r in done.values()),'empty':sum(r['status']=='empty' for r in done.values()),'failed':0,'startedAt':time.strftime('%Y-%m-%dT%H:%M:%S%z'),'current':None}
from PIL import Image

def encode_render(source,destination):
    with Image.open(source) as raw:
        im=raw.convert('RGBA')
        if im.size!=(args.size,args.size):im=im.resize((args.size,args.size),Image.Resampling.LANCZOS)
        if im.getchannel('A').getextrema()[1]==0:return {'empty':True}
        if im.getchannel('A').getextrema()[0]!=0:raise ValueError('Render background is not transparent')
        temp=destination.with_name(destination.name+'.tmp')
        im.save(temp,format='WEBP',lossless=True,quality=75,method=4,exact=True)
    os.replace(temp,destination)
    return {'bytes':destination.stat().st_size}

status_path=args.out/'status.json';start=time.monotonic();session_saved=0
def status():
    state['updatedAt']=time.strftime('%Y-%m-%dT%H:%M:%S%z');state['elapsedSeconds']=round(time.monotonic()-start,1);state['sessionSaved']=session_saved
    temp=status_path.with_suffix(f'.{os.getpid()}.tmp');temp.write_text(json.dumps(state,ensure_ascii=False,indent=2),encoding='utf-8')
    for attempt in range(8):
        try:os.replace(temp,status_path);return
        except PermissionError:time.sleep(.05*(attempt+1))
    temp.unlink(missing_ok=True)
def publish_gallery():
    rows=[r for r in done.values() if r['status']=='saved']
    data={'status':state,'items':rows}
    dest=args.out/'catalog-data.js';temp=dest.with_suffix(f'.{os.getpid()}.tmp');temp.write_text('window.CLOTHING_CATALOG='+json.dumps(data,ensure_ascii=False)+';',encoding='utf-8')
    for attempt in range(8):
        try:os.replace(temp,dest);return
        except PermissionError:time.sleep(.05*(attempt+1))
    print('CATALOG_PUBLISH_DEFERRED: browser is reading the catalog file',flush=True)
    temp.unlink(missing_ok=True)
def record(row):
    row['createdAt']=time.strftime('%Y-%m-%dT%H:%M:%S%z')
    with manifest.open('a',encoding='utf-8') as fp:fp.write(json.dumps(row,ensure_ascii=False)+'\n')
    done[row['key']]=row
def clear_model():
    for obj in list(bpy.data.objects):
        if obj.name not in studio_objects:bpy.data.objects.remove(obj,do_unlink=True)
    if hasattr(scene,'sz_txds'):
        txds=scene.sz_txds.texture_dictionaries
        for i in reversed(range(len(txds))):txds.remove(i)
    bpy.data.orphans_purge(do_recursive=True)
def extract(source,destination):
    destination.write_bytes(VPath(source).read_bytes());return destination
def load_texture_dictionary(source):
    asset=try_load_asset(VPath(source));images={}
    if not asset or not hasattr(asset,'textures'):raise RuntimeError('Texture dictionary could not be read: '+source)
    for tex in asset.textures.values():
        if not tex.data:continue
        with tex.data.open() as src:dds=src.read()
        image=bpy.data.images.new(tex.name+'.dds',width=1,height=1);image.source='FILE';image.filepath='//'+tex.name+'.dds';image.pack(data=dds,data_len=len(dds));image.colorspace_settings.name='sRGB';images[tex.name.lower()]=image
    return images
def skin_mask(mat):
    node=mat.node_tree.nodes.get('SpecSampler')
    if not node or not node.image:return None
    image=node.image
    if image.size[0]<2:return None
    pixels=np.array(image.pixels[:],dtype=np.float32).reshape(image.size[1],image.size[0],4)
    # Freemode skin uses the characteristic red/blue specular encoding. Alpha is gloss,
    # and treating alpha as a body mask incorrectly removes latex masks and leather gloves.
    skin=(pixels[:,:,0]>.4)&(pixels[:,:,2]>.65)&(pixels[:,:,1]<.35)&(pixels[:,:,0]>pixels[:,:,1]*2)
    if not skin.any():return None
    keep=(~skin).astype(np.float32)
    rgba=np.ones_like(pixels);rgba[:,:,:3]=keep[:,:,None]
    mask_image=bpy.data.images.new(mat.name+' body exclusion',width=image.size[0],height=image.size[1],alpha=False)
    mask_image.colorspace_settings.name='Non-Color';mask_image.pixels.foreach_set(rgba.ravel())
    return keep,mask_image
def prepare_meshes(job,first_images):
    def used_materials():
        materials={};usage={}
        for obj in scene.objects:
            if obj.type!='MESH':continue
            for polygon in obj.data.polygons:
                if polygon.material_index>=len(obj.data.materials):continue
                mat=obj.data.materials[polygon.material_index]
                if mat:materials[mat.name]=mat;usage[mat.name]=usage.get(mat.name,0)+1
        return materials,usage
    materials,usage=used_materials()
    skins={};delete_materials=set();placeholders=set();bindings=[]
    is_r=bool(re.search(r'_r(?:_\d+)?\.ydd$',job['model']['name']))
    for mat in materials.values():
        shader_name=mat.shader_properties.filename
        diffuse_node=mat.node_tree.nodes.get('DiffuseSampler')
        diffuse=diffuse_node.image if diffuse_node else None
        if mat.name.split('.')[0]=='blank' and shader_name=='default.sps' and usage.get(mat.name,0)<=4 and (not diffuse or diffuse.size[0]<2):
            delete_materials.add(mat.name);placeholders.add(mat.name);job['_sourcePlaceholder']=True;continue
        if 'skin' in shader_name or shader_name.startswith('ped_hair'):delete_materials.add(mat.name);continue
        if is_r and shader_name in {'ped.sps','ped_cutout.sps'}:
            mask=skin_mask(mat)
            if mask is not None:skins[mat.name]=mask
    removed=0
    for obj in list(scene.objects):
        if obj.type!='MESH':continue
        mesh=obj.data;bm=bmesh.new();bm.from_mesh(mesh);uv=bm.loops.layers.uv.active;faces=[]
        for face in bm.faces:
            if face.material_index>=len(mesh.materials):continue
            mat=mesh.materials[face.material_index]
            if not mat:continue
            if mat.name in delete_materials:faces.append(face);continue
            if uv and mat.name in skins:
                arr,_=skins[mat.name];h,w=arr.shape;uvs=np.array([loop[uv].uv[:] for loop in face.loops]);center=uvs.mean(0)
                samples=np.concatenate([center[None,:],uvs*.7+center*.3]);xx=np.clip((samples[:,0]*w).astype(int),0,w-1);yy=np.clip((samples[:,1]*h).astype(int),0,h-1)
                if np.median(arr[yy,xx])<.5:faces.append(face)
        # A bare arm/leg mesh can leave tiny nails after skin removal. Such remnants are not clothing.
        face_set=set(faces);original_area=sum(f.calc_area() for f in bm.faces);remaining_area=sum(f.calc_area() for f in bm.faces if f not in face_set)
        if faces and remaining_area<original_area*.025:faces=list(bm.faces)
        removed+=len(faces);bmesh.ops.delete(bm,geom=faces,context='FACES');unused=[v for v in bm.verts if not v.link_faces];bmesh.ops.delete(bm,geom=unused,context='VERTS');bm.to_mesh(mesh);bm.free();mesh.update()
        for p in mesh.polygons:p.use_smooth=True
    # Empty slots and materials from removed geometry must not require a texture.
    materials,_=used_materials()
    for mat in materials.values():
        if mat.name in delete_materials:continue
        nodes=mat.node_tree.nodes;links=mat.node_tree.links
        def image_node(name):
            n=nodes.get(name);return n.image if n and n.type=='TEX_IMAGE' else None
        diffuse,bump=image_node('DiffuseSampler'),image_node('BumpSampler');shader_name=mat.shader_properties.filename
        if not diffuse or diffuse.size[0]<2:
            old_name=diffuse.name.split('.dds')[0].lower() if diffuse else mat.name.lower()
            replacement=first_images.get(old_name)
            prefix=old_name.split('_diff_')[0]+'_diff_' if '_diff_' in old_name else None
            if replacement is None and prefix:
                matches=[im for name,im in first_images.items() if name.startswith(prefix)]
                if len(matches)==1:replacement=matches[0]
            if replacement is None and len(first_images)==1 and shader_name.startswith('ped'):
                replacement=next(iter(first_images.values()))
            if replacement is not None:diffuse=replacement
        if not diffuse or diffuse.size[0]<2:raise RuntimeError('Missing diffuse texture: '+mat.name)
        texture_name=diffuse.name.split('.dds')[0].lower();nodes.clear()
        out=nodes.new('ShaderNodeOutputMaterial');bs=nodes.new('ShaderNodeBsdfPrincipled');tex=nodes.new('ShaderNodeTexImage');tex.name='Catalog Diffuse';tex.image=diffuse;diffuse.colorspace_settings.name='sRGB'
        links.new(tex.outputs['Color'],bs.inputs['Base Color']);links.new(bs.outputs[0],out.inputs['Surface']);bs.inputs['Alpha'].default_value=1;bs.inputs['Roughness'].default_value=.76;bs.inputs['Specular IOR Level'].default_value=.25
        bindings.append((tex,texture_name))
        if mat.name in skins:
            spec=skins[mat.name][1];st=nodes.new('ShaderNodeTexImage');st.image=spec;st.interpolation='Closest';threshold=nodes.new('ShaderNodeMath');threshold.operation='GREATER_THAN';threshold.inputs[1].default_value=.5;links.new(st.outputs['Color'],threshold.inputs[0]);links.new(threshold.outputs[0],bs.inputs['Alpha'])
        else:
            shader=ShaderManager.find_shader(shader_name)
            if shader and (shader.is_cutout or shader.is_alpha or shader.is_decal):
                threshold=nodes.new('ShaderNodeMath');threshold.operation='GREATER_THAN';threshold.inputs[1].default_value=.33;links.new(tex.outputs['Alpha'],threshold.inputs[0]);links.new(threshold.outputs[0],bs.inputs['Alpha'])
        if bump and bump.size[0]>1:
            bump.colorspace_settings.name='Non-Color';nt=nodes.new('ShaderNodeTexImage');nt.image=bump
            sep=nodes.new('ShaderNodeSeparateColor');comb=nodes.new('ShaderNodeCombineColor');inv=nodes.new('ShaderNodeMath');inv.operation='SUBTRACT';inv.inputs[0].default_value=1
            links.new(nt.outputs['Color'],sep.inputs[0]);links.new(sep.outputs[0],comb.inputs[0]);links.new(sep.outputs[1],inv.inputs[1]);links.new(inv.outputs[0],comb.inputs[1]);links.new(sep.outputs[2],comb.inputs[2])
            nm=nodes.new('ShaderNodeNormalMap');nm.inputs['Strength'].default_value=.6;links.new(comb.outputs[0],nm.inputs['Color']);links.new(nm.outputs['Normal'],bs.inputs['Normal'])
    return bindings,removed
def frame(job):
    if job['part'].startswith('p_'):
        rotation=Matrix.Rotation(math.pi/2,4,'Y')
        for obj in scene.objects:
            if obj.name not in studio_objects and obj.parent is None:obj.matrix_world=rotation@obj.matrix_world
    meshes=[obj for obj in scene.objects if obj.type=='MESH' and len(obj.data.polygons)>0 and not obj.hide_render]
    if not meshes:return False
    bpy.context.view_layer.update();points=[obj.matrix_world@Vector(v) for obj in meshes for v in obj.bound_box]
    low=Vector(tuple(min(v[i] for v in points) for i in range(3)));high=Vector(tuple(max(v[i] for v in points) for i in range(3)));center=(low+high)/2
    if (high-low).length<.001:return False
    if job['category']=='bags' and sum(len(o.data.polygons) for o in meshes)<=4 and (high-low).length<.1:return False
    if job['collection'] in {'mp_m_freemode_01','mp_f_freemode_01'} and (job['category']!='decals' or job['drawable']==0) and sum(len(o.data.polygons) for o in meshes)<=4 and (high-low).length<.1:return False
    rear=-1 if job['category']=='bags' else 1
    camera.location=center+Vector((2.5*rear,-6*rear,1));camera.rotation_euler=(center-camera.location).to_track_quat('-Z','Y').to_euler()
    bpy.context.view_layer.update();projected=[camera.matrix_world.inverted()@p for p in points];camera_data.ortho_scale=max(max(v.x for v in projected)-min(v.x for v in projected),max(v.y for v in projected)-min(v.y for v in projected))*1.15
    for obj,pos in lights:obj.location=center+Vector((pos.x*rear,pos.y*rear,pos.z));obj.rotation_euler=(center-obj.location).to_track_quat('-Z','Y').to_euler()
    return True

status();publish_gallery();jobs=plan['jobs']
if args.only_keys:
    selected=set(json.loads(args.only_keys.read_text(encoding='utf-8')));jobs=[j for j in jobs if j['key'] in selected]
jobs=jobs[args.start_job:args.start_job+args.limit_jobs if args.limit_jobs else None]
for job_number,job in enumerate(jobs,start=args.start_job):
    if (args.out/'STOP').exists():state['status']='stopped';status();break
    variants=job['textures'] or [None]
    if args.max_variants:variants=variants[:args.max_variants]
    todo=[(t.get('textureId',i) if t else 0,t) for i,t in enumerate(variants) if f"{job['key']}/{t.get('textureId',i) if t else 0}" not in done]
    if not todo:continue
    state['current']={'job':job_number,'key':job['key']};status();previous_images=[]
    try:
        clear_model()
        for f in args.scratch.iterdir():
            if f.is_file() and f.suffix.lower() in {'.ydd','.ytd','.yft'}:f.unlink()
        model=extract(job['model']['path'],args.scratch/job['model']['name'])
        skeleton_key=job['gender']+':'+('mp_m_freemode_01' if job['gender']=='male' else 'mp_f_freemode_01')
        skeleton_source=plan.get('skeletons',{}).get(skeleton_key)
        if skeleton_source:extract(skeleton_source,args.scratch/Path(skeleton_source).name)
        first=variants[0];files=[{'name':model.name}]
        if first:
            tex_file=extract(first['path'],args.scratch/first['name']);files.append({'name':tex_file.name})
        bpy.ops.sollumz.import_assets(directory=str(args.scratch),files=files,use_custom_settings=True,dwd_import_external_skeleton='FROM_DIR' if skeleton_source else 'NO',split_by_group=False,textures_mode='PACK')
        first_images=load_texture_dictionary(first['path']) if first else {}
        bindings,removed=prepare_meshes(job,first_images);has_geometry=frame(job)
        for texture_id,texture in todo:
            if (args.out/'STOP').exists():break
            key=f"{job['key']}/{texture_id}";row={'key':key,'gender':job['gender'],'category':job['category'],'collection':job['collection'],'drawableLocal':job['drawable'],'texture':texture_id,'model':job['model']['name'],'textureAsset':texture['name'] if texture else None,'removedSkinFaces':removed,'size':args.size,'angle':22,'background':'transparent','transparent':True,'lossless':True,'status':'empty' if not has_geometry else 'saved','path':None}
            if not has_geometry:
                if job.get('_sourcePlaceholder'):row['reason']='source model is an empty placeholder'
                record(row);state['empty']+=1;status();continue
            images=load_texture_dictionary(texture['path']) if texture else {}
            for node,old_name in bindings:
                # Every texture file provides the matching variant under its own texture name.
                replacement=images.get(old_name)
                if replacement is None:
                    prefix=old_name.split('_diff_')[0]+'_diff_' if '_diff_' in old_name else None
                    candidates=[im for name,im in images.items() if prefix and name.startswith(prefix)]
                    if len(candidates)==1:replacement=candidates[0]
                    elif len(images)==1:replacement=next(iter(images.values()))
                if replacement is not None:node.image=replacement
                elif texture:raise RuntimeError('Variant diffuse could not be matched: '+old_name+' / '+texture['name'])
            for im in previous_images:
                if im.users==0:bpy.data.images.remove(im)
            previous_images=list(images.values())
            # Revisions never overwrite files referenced by an older resume record.
            revision=job['key'].rsplit('@',1)[-1]
            rel=Path(job['gender'])/job['category']/job['collection']/revision/f"{job['drawable']:03d}_{texture_id:02d}.webp";dest=args.out/rel;dest.parent.mkdir(parents=True,exist_ok=True)
            intermediate=args.scratch/'current-render.png'
            scene.render.filepath=str(intermediate);state['current'].update({'texture':texture_id,'path':rel.as_posix()});status();render_start=time.monotonic();bpy.ops.render.render(write_still=True)
            encoded=encode_render(intermediate,dest);intermediate.unlink(missing_ok=True)
            if encoded.get('empty'):
                row.update(status='empty',reason='no visible pixels');record(row);state['empty']+=1;status();continue
            row.update(path=rel.as_posix(),format='webp',bytes=encoded['bytes']);row['renderSeconds']=round(time.monotonic()-render_start,3);record(row);state['saved']+=1;session_saved+=1;status()
            if session_saved%25==0:publish_gallery()
            print('CATALOG_SAVED',state['saved'],key,row['renderSeconds'],flush=True)
    except Exception as exc:
        state['failed']+=1;state['lastError']={'key':job['key'],'message':str(exc)};status()
        with (args.out/'errors.jsonl').open('a',encoding='utf-8') as fp:fp.write(json.dumps({'key':job['key'],'error':str(exc),'traceback':traceback.format_exc()})+'\n')
        traceback.print_exc()
else:
    state['status']='preview-complete' if args.max_variants or 'preview' in args.plan.name else ('chunk-complete' if args.limit_jobs else ('complete' if state['failed']==0 else 'complete-with-errors'));state['current']=None;status()
if (args.out/'STOP').exists():state['status']='stopped';status()
publish_gallery()

print('CATALOG_DONE',json.dumps(state,ensure_ascii=False),flush=True)
