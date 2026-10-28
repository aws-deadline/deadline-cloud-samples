-- Render frame 0 of the scene loaded by 3dsmaxbatch -sceneFile through RenderCam.
-- Run with: 3dsmaxbatch.exe render_scene.ms -sceneFile <scene.max>   (P4_IMG = output image path)
(
    fn logLine msg = format "P4 %\n" msg

    local img = systemTools.getEnvVariable "P4_IMG"
    if img == undefined or img == "" do throw "P4_IMG is not set"

    logLine ("renderer.current: " + (renderers.current as string))
    logLine ("vrayVersion: " + (try ((vrayVersion()) as string) catch "unavailable"))
    if not (matchPattern (renderers.current as string) pattern:"V_Ray_*") do throw "scene renderer is not V-Ray"
    for p in #("ColorPipelineMode", "Mode", "OCIOConfigPath", "ConfigPath") do (
        local v = try ((getProperty ColorPipelineMgr (p as name)) as string) catch undefined
        if v != undefined do logLine ("ColorPipelineMgr." + p + " = " + v)
    )

    local cam = getNodeByName "RenderCam"
    if cam == undefined do throw "RenderCam not found in scene"
    local t0 = timeStamp()
    local bmp = render camera:cam outputfile:img outputwidth:640 outputheight:360 frame:0 vfb:false quiet:true
    logLine ("render returned: " + (bmp as string) + "  ms: " + ((timeStamp() - t0) as string))
    logLine ("output exists: " + ((doesFileExist img) as string))
    if not (doesFileExist img) do throw ("render wrote no image: " + img)
)
