-- Research-only replacement bridge for a copied GIANTS Editor scene.
--
-- The launcher provides PROBE_ROOT, PROBE_EXPECTED_SCENE and
-- PROBE_EXPECTED_TARGET. The launcher snapshots replacement.xml as
-- input-replacement.xml beneath PROBE_ROOT; that immutable input has a
-- <replacement targetPath="Root/door" donorPath="Root/donorDoor"
-- donorFile="C:/copied/donor.i3d" replacementName="researchReplacement"/>
-- element.  Paths name every node from the first scene-root child.  The
-- selected target and donor subtrees must be rigid and have zero local
-- rotation. The imported clone is linked beneath the target parent.  This bridge does not support axis permutations or skinned
-- meshes.

local base=assert(PROBE_ROOT,"missing_probe_root")
local expectedScene=assert(PROBE_EXPECTED_SCENE,"missing_probe_expected_scene")
local expectedTarget=assert(PROBE_EXPECTED_TARGET,"missing_probe_expected_target")
local initialized,lastSequence,saveSequence=false,nil,0
local replacement,target,parent,config=nil,nil,nil,nil

local function normalized(value) return string.lower(string.gsub(value or "","\\","/")) end
local function finite(value) return value~=nil and value==value and value~=math.huge and value~=-math.huge end
local function near(value,expected) return math.abs(value-expected)<0.000001 end
local function zeroRotation(node)
    local x,y,z=getRotation(node)
    return near(x,0) and near(y,0) and near(z,0)
end
local function text(value) if value==nil then return "" end;return tostring(value) end

local function writeXml(filename,values)
    if values.clock==nil and type(getTime)=="function" then
        local ok,clock=pcall(getTime)
        if ok and finite(clock) then values.clock=clock end
    end
    local xml=createXMLFile("replacementProbe",base..filename,"probe")
    for key,value in pairs(values) do setXMLString(xml,"probe."..key,text(value)) end
    saveXMLFile(xml);delete(xml)
end

local function json(value)
    local kind=type(value)
    if kind=="nil" then return "null" end
    if kind=="boolean" then return value and "true" or "false" end
    if kind=="number" then return finite(value) and string.format("%.9g",value) or "null" end
    if kind=="string" then
        return '"'..value:gsub("\\","\\\\"):gsub('"','\\"'):gsub("\n","\\n"):gsub("\r","\\r"):gsub("\t","\\t")..'"'
    end
    local array=true;local count=0
    for key,_ in pairs(value) do count=count+1;if type(key)~="number" then array=false;break end end
    local out={}
    if array then for index=1,count do out[#out+1]=json(value[index]) end;return "["..table.concat(out,",").."]" end
    for key,item in pairs(value) do out[#out+1]=json(tostring(key))..":"..json(item) end
    return "{"..table.concat(out,",").."}"
end

local function writeSnapshot(sequence,snapshot)
    local ok,reason=pcall(function()
        local xml=createXMLFile("replacementSnapshot",base..string.format("snapshot-%06d.xml",sequence),"probe")
        setXMLString(xml,"probe.json",json(snapshot))
        saveXMLFile(xml);delete(xml)
    end)
    if not ok then return nil,"snapshot_write_failed:"..text(reason) end
    return true
end

local function firstSceneChild(root)
    if getNumOfChildren(root)<1 then return nil end
    return getChildAt(root,0)
end

local function pathNode(root,path)
    local current=firstSceneChild(root)
    if not current or path==nil or path=="" then return nil end
    local parts={}
    for part in string.gmatch(path,"[^/]+") do parts[#parts+1]=part end
    for partIndex,part in ipairs(parts) do
        if getName(current)~=part then return nil end
        if partIndex<#parts then
            local child=nil
            for index=0,getNumOfChildren(current)-1 do
                local candidate=getChildAt(current,index)
                if getName(candidate)==parts[partIndex+1] then
                    if child then return nil end
                    child=candidate
                end
            end
            if not child then return nil end
            current=child
        else return current end
    end
    return nil
end

local function include(bounds,x,y,z)
    if not finite(x) or not finite(y) or not finite(z) then return nil,"nonfinite_vertex" end
    if not bounds then return {minX=x,minY=y,minZ=z,maxX=x,maxY=y,maxZ=z} end
    bounds.minX=math.min(bounds.minX,x);bounds.minY=math.min(bounds.minY,y);bounds.minZ=math.min(bounds.minZ,z)
    bounds.maxX=math.max(bounds.maxX,x);bounds.maxY=math.max(bounds.maxY,y);bounds.maxZ=math.max(bounds.maxZ,z)
    return bounds
end

local function boundsFor(node,coordinateParent)
    local pending={node};local cursor=1;local bounds=nil;local shapeCount=0;local vertexCount=0
    while cursor<=#pending do
        local item=pending[cursor];cursor=cursor+1
        if getHasClassId(item,ClassIds.SHAPE) and not getIsNonRenderable(item) then
            local count,positions=getShapeVertexPositions(item)
            if count==nil or positions==nil then return nil,"vertex_positions_unavailable" end
            shapeCount=shapeCount+1;vertexCount=vertexCount+count
            for index=1,count*3,3 do
                local x,y,z=localToLocal(item,coordinateParent,positions[index],positions[index+1],positions[index+2])
                local reason
                bounds,reason=include(bounds,x,y,z)
                if not bounds then return nil,reason end
            end
        end
        for index=0,getNumOfChildren(item)-1 do pending[#pending+1]=getChildAt(item,index) end
    end
    if not bounds then return nil,"subtree_has_no_vertices" end
    bounds.width=bounds.maxX-bounds.minX;bounds.height=bounds.maxY-bounds.minY;bounds.depth=bounds.maxZ-bounds.minZ
    bounds.centerX=(bounds.minX+bounds.maxX)/2;bounds.centerY=(bounds.minY+bounds.maxY)/2;bounds.centerZ=(bounds.minZ+bounds.maxZ)/2
    bounds.shapeCount=shapeCount;bounds.vertexCount=vertexCount
    return bounds
end

local function collectSnapshot()
    local root=getRootNode();local rows={};local pending={{node=root,path=""}};local cursor=1
    while cursor<=#pending do
        if #rows>=10000 then return nil,"node_cap_exceeded" end
        local item=pending[cursor];cursor=cursor+1
        local x,y,z=getTranslation(item.node);local rx,ry,rz=getRotation(item.node);local sx,sy,sz=getScale(item.node)
        local shape=getHasClassId(item.node,ClassIds.SHAPE);local nonRenderable=shape and getIsNonRenderable(item.node) or false
        local visible=getVisibility(item.node)
        local vertices,materials,digest=0,0,1
        if shape then
            local positions
            vertices,positions=getShapeVertexPositions(item.node)
            if vertices==nil or positions==nil then return nil,"vertex_positions_unavailable" end
            materials=getNumOfMaterials(item.node)
            for index=1,vertices*3 do digest=(digest*131+math.floor(positions[index]*1000000+0.5))%2147483647 end
        end
        rows[#rows+1]={path=item.path,name=getName(item.node),translation={x,y,z},rotation={rx,ry,rz},scale={sx,sy,sz},visible=visible,shape=shape,nonRenderable=nonRenderable,vertices=vertices,materials=materials,vertexDigest=digest}
        for index=0,getNumOfChildren(item.node)-1 do
            local child=getChildAt(item.node,index)
            pending[#pending+1]={node=child,path=item.path=="" and getName(child) or item.path.."/"..getName(child)}
        end
    end
    local out={scene=getSceneFilename(),nodes=rows}
    if target and parent then out.targetBounds=boundsFor(target,parent) end
    if replacement and parent then out.replacementBounds=boundsFor(replacement,parent) end
    return out
end

local function loadConfig()
    local xml=loadXMLFile("replacementConfig",base.."input-replacement.xml")
    if not xml or xml==0 then return nil,"replacement_config_unreadable" end
    local value={targetPath=getXMLString(xml,"replacement#targetPath"),donorPath=getXMLString(xml,"replacement#donorPath"),donorFile=getXMLString(xml,"replacement#donorFile"),replacementName=getXMLString(xml,"replacement#replacementName")}
    value.cameraX=tonumber(getXMLString(xml,"replacement#cameraX"));value.cameraY=tonumber(getXMLString(xml,"replacement#cameraY"));value.cameraZ=tonumber(getXMLString(xml,"replacement#cameraZ"))
    value.directionX=tonumber(getXMLString(xml,"replacement#directionX"));value.directionY=tonumber(getXMLString(xml,"replacement#directionY"));value.directionZ=tonumber(getXMLString(xml,"replacement#directionZ"))
    value.overviewCameraX=tonumber(getXMLString(xml,"replacement#overviewCameraX"));value.overviewCameraY=tonumber(getXMLString(xml,"replacement#overviewCameraY"));value.overviewCameraZ=tonumber(getXMLString(xml,"replacement#overviewCameraZ"))
    value.overviewDirectionX=tonumber(getXMLString(xml,"replacement#overviewDirectionX"));value.overviewDirectionY=tonumber(getXMLString(xml,"replacement#overviewDirectionY"));value.overviewDirectionZ=tonumber(getXMLString(xml,"replacement#overviewDirectionZ"))
    delete(xml)
    if not value.targetPath or value.targetPath=="" or not value.donorPath or value.donorPath=="" or not value.donorFile or value.donorFile=="" then return nil,"replacement_config_missing_required_attribute" end
    if not value.replacementName or value.replacementName=="" then value.replacementName="researchReplacement" end
    return value
end

local function initialize()
    if initialized then return true end
    if normalized(getSceneFilename())~=normalized(expectedScene) then return nil,"unexpected_scene" end
    local root=getRootNode();local first=firstSceneChild(root)
    if not first or getName(first)~=expectedTarget then return nil,"unexpected_scene_root" end
    local loaded,reason=loadConfig()
    if not loaded then return nil,reason end
    config=loaded
    local prefix=normalized(base):gsub("/+$","").."/"
    local donor=normalized(config.donorFile)
    if donor:sub(1,#prefix)~=prefix or donor:find("/%.%./") then return nil,"donor_outside_case" end
    target=pathNode(root,config.targetPath)
    if target then
        parent=getParent(target)
    else
        replacement=pathNode(root,config.targetPath:gsub("[^/]+$",config.replacementName))
        if replacement then parent=getParent(replacement) end
    end
    initialized=true
    writeXml("ready.xml",{ok=true,op="ready",scene=getSceneFilename(),expectedTarget=expectedTarget,replacementName=config.replacementName,replacementPresent=replacement~=nil})
    return true
end

local function resolveTarget(required)
    local root=getRootNode();target=pathNode(root,config.targetPath)
    if target then parent=getParent(target);return target end
    if required then return nil,"target_path_missing" end
    replacement=pathNode(root,config.targetPath:gsub("[^/]+$",config.replacementName))
    return replacement
end

local function importDonor()
    local found,reason=resolveTarget(true);if not found then return nil,reason end
    if replacement then return nil,"replacement_already_imported" end
    local loaded,failedReason=loadI3DFile(config.donorFile,false,false,true)
    if not loaded or loaded==0 then return nil,"donor_load_failed:"..text(failedReason) end
    local donor=pathNode(loaded,config.donorPath)
    if not donor then delete(loaded);return nil,"donor_path_missing" end
    if not zeroRotation(target) or not zeroRotation(donor) then delete(loaded);return nil,"rotation_not_supported" end
    local clone=clone(donor,false,false,false)
    if not clone or clone==0 then delete(loaded);return nil,"donor_clone_failed" end
    unlink(clone)
    local index=getChildIndex(target)
    if index==nil then delete(clone);delete(loaded);return nil,"target_parent_changed" end
    link(parent,clone,index);setName(clone,config.replacementName)
    local rx,ry,rz=getRotation(target);setRotation(clone,rx,ry,rz)
    delete(loaded)
    replacement=clone
    return true
end

local function fitDonor()
    if not target or not replacement or not parent then return nil,"import_required" end
    if not zeroRotation(target) or not zeroRotation(replacement) then return nil,"rotation_not_supported" end
    local tx,ty,tz=getTranslation(target);setTranslation(replacement,tx,ty,tz)
    local targetBounds,reason=boundsFor(target,parent);if not targetBounds then return nil,reason end
    local donorBounds;donorBounds,reason=boundsFor(replacement,parent);if not donorBounds then return nil,reason end
    if donorBounds.width<=0.000001 or donorBounds.height<=0.000001 then return nil,"degenerate_donor_extent" end
    if targetBounds.width<=0.000001 or targetBounds.height<=0.000001 then return nil,"degenerate_target_extent" end
    local sx,sy,sz=getScale(replacement);setScale(replacement,sx*targetBounds.width/donorBounds.width,sy*targetBounds.height/donorBounds.height,sz)
    donorBounds,reason=boundsFor(replacement,parent);if not donorBounds then return nil,reason end
    local rx,ry,rz=getTranslation(replacement)
    setTranslation(replacement,rx+targetBounds.centerX-donorBounds.centerX,ry+targetBounds.centerY-donorBounds.centerY,rz+targetBounds.centerZ-donorBounds.centerZ)
    donorBounds,reason=boundsFor(replacement,parent);if not donorBounds then return nil,reason end
    return targetBounds,donorBounds
end

local function replaceTarget()
    if not target or not replacement or not parent then return nil,"fit_required" end
    local a,reason=boundsFor(target,parent);if not a then return nil,reason end
    local b;b,reason=boundsFor(replacement,parent);if not b then return nil,reason end
    if math.abs(a.width-b.width)>0.0005 or math.abs(a.height-b.height)>0.0005 or math.abs(a.centerX-b.centerX)>0.0005 or math.abs(a.centerY-b.centerY)>0.0005 then return nil,"fit_tolerance_failed" end
    delete(target);target=nil
    return true
end

local function render(sequence,kind)
    if not replacement and not target then return nil,"render_target_missing" end
    local x,y,z=config.cameraX,config.cameraY,config.cameraZ
    local dx,dy,dz=config.directionX,config.directionY,config.directionZ
    if kind=="overview" then
        x,y,z=config.overviewCameraX,config.overviewCameraY,config.overviewCameraZ
        dx,dy,dz=config.overviewDirectionX,config.overviewDirectionY,config.overviewDirectionZ
    end
    if not(finite(x) and finite(y) and finite(z) and finite(dx) and finite(dy) and finite(dz)) then return nil,"camera_config_missing" end
    local camera=getCamera();setWorldTranslation(camera,x,y,z);setWorldDirection(camera,dx,dy,dz,0,1,0);refreshViewport()
    renderScreenshot(base..string.format("view-%06d.png",sequence),1024,768,1,"raw_alpha",0,0,0,0,0,3,12,false)
    return true
end

local function slowMutate()
    if not replacement then return nil,"replacement_missing" end
    if type(getTime)~="function" then return nil,"engine_time_unavailable" end
    local start=getTime()
    if not finite(start) then return nil,"engine_time_invalid" end
    local x,y,z=getTranslation(replacement);setTranslation(replacement,x+0.01,y,z)
    local untilTime=start+4.0;local iterations=0
    while getTime()<untilTime and iterations<100000000 do iterations=iterations+1 end
    local finished=getTime()
    return {changedCount=1,elapsedClock=finished-start,loopIterations=iterations}
end

local function dispatch()
    local requestPath=base.."request.xml";if not fileExists(requestPath) then return end
    local xml=loadXMLFile("replacementRequest",requestPath)
    if not xml or xml==0 then writeXml("response-000000.xml",{ok=false,error="request_unreadable"});return end
    local sequence=getXMLInt(xml,"request#seq") or 0;local op=getXMLString(xml,"request#op") or "";local kind=getXMLString(xml,"request#kind") or ""
    if sequence<1 or sequence>100000 then delete(xml);return end
    local receipt=base..string.format("response-%06d.xml",sequence)
    if lastSequence==sequence or fileExists(receipt) then delete(xml);return end
    local initializedOk,initializedReason=initialize()
    if not initializedOk then
        writeXml(string.format("response-%06d.xml",sequence),{ok=false,seq=sequence,op=op,scene=getSceneFilename(),error=initializedReason})
        delete(xml);return
    end
    local result={ok=false,seq=sequence,op=op,scene=getSceneFilename()};local snapshot=nil
    local success,value,operationReason=pcall(function()
        if op=="inspect" then return true
        elseif op=="import" then return importDonor()
        elseif op=="fit" then return fitDonor()
        elseif op=="replace" then return replaceTarget()
        elseif op=="render" then return render(sequence,kind)
        elseif op=="slow-mutate" then return slowMutate()
        elseif op=="quit" then return true
        else return nil,"unsupported_operation" end
    end)
    if success and value then result.ok=true
    elseif success then result.error=text(operationReason or "operation_failed")
    else result.error="operation_error:"..text(value) end
    if type(value)=="table" then
        if value.changedCount then result.changedCount=value.changedCount end
        if value.elapsedClock then result.elapsedClock=value.elapsedClock end
        if value.loopIterations then result.loopIterations=value.loopIterations end
    end
    local snapOk,snapValue,snapReason=pcall(collectSnapshot)
    if snapOk and snapValue then snapshot=snapValue
    elseif snapOk then result.ok=false;result.error="snapshot_failed:"..text(snapReason)
    else result.ok=false;result.error="snapshot_error:"..text(snapValue) end
    if snapshot then
        local wrote,writeReason=writeSnapshot(sequence,snapshot)
        if not wrote then result.ok=false;result.error=writeReason end
        if snapshot.targetBounds then result.targetWidth=snapshot.targetBounds.width;result.targetHeight=snapshot.targetBounds.height end
        if snapshot.replacementBounds then result.replacementWidth=snapshot.replacementBounds.width;result.replacementHeight=snapshot.replacementBounds.height end
    end
    writeXml(string.format("response-%06d.xml",sequence),result);lastSequence=sequence;delete(xml)
    if op=="quit" and result.ok then writeXml("done.xml",{ok=true,op="done",seq=sequence,scene=getSceneFilename()});editorExit(0) end
end

MCP_NATIVE_DISPATCH=dispatch
addEventListener(HookType.ON_FILE_OPEN,function() pcall(initialize) end)
addEventListener(HookType.ON_SAVE,function(path)
    if not initialized then return end
    saveSequence=saveSequence+1
    writeXml(string.format("save-%06d.xml",saveSequence),{ok=true,op="save",seq=saveSequence,scene=getSceneFilename(),path=path,replacementPresent=replacement~=nil})
end)
pcall(initialize)
