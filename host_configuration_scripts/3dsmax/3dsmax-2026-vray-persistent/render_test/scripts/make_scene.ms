-- Build a minimal V-Ray scene for 3ds Max 2026 and save it as a .max file.
-- Run with: 3dsmaxbatch.exe make_scene.ms   (P4_SCENE = output .max path)
-- The scene is created from a reset file, so color management is the 3ds Max 2026 built-in
-- default and nothing points at an external OCIO config. The ColorPipelineMgr properties are
-- printed so the listener log records which mode and config the saved scene carries.
(
    fn logLine msg = format "P4 %\n" msg

    fn dumpColorPipeline = (
        local ss = stringStream ""
        try (showInterface ColorPipelineMgr to:ss) catch (logLine ("showInterface ColorPipelineMgr failed: " + getCurrentException()))
        local text = ss as string
        logLine "ColorPipelineMgr interface:"
        format "%\n" text
        -- Print every readable property's value. Property lines look like "   .Name : type : Read|..."
        for ln in (filterString text "\n") do (
            local t = trimLeft ln
            if t.count > 1 and t[1] == "." and (findString t ": Read") != undefined do (
                local pname = trimRight (substring t 2 ((findString t " : ") - 2))
                local v = try ((getProperty ColorPipelineMgr (pname as name)) as string) catch ("<error: " + getCurrentException() + ">")
                logLine ("ColorPipelineMgr." + pname + " = " + v)
            )
        )
    )

    local scenePath = systemTools.getEnvVariable "P4_SCENE"
    if scenePath == undefined or scenePath == "" do throw "P4_SCENE is not set"

    resetMaxFile #noPrompt
    logLine ("maxVersion: " + ((maxVersion()) as string))
    logLine ("vrayVersion: " + (try ((vrayVersion()) as string) catch "unavailable"))
    dumpColorPipeline()

    -- Pick the CPU V-Ray renderer class from what is installed, not a hard-coded name.
    local vr = for c in RendererClass.classes where matchPattern (c as string) pattern:"V_Ray_*" and not matchPattern (c as string) pattern:"V_Ray_GPU*" collect c
    logLine ("V-Ray CPU renderer classes: " + (vr as string))
    if vr.count == 0 do throw "no V-Ray CPU renderer class is registered"
    renderers.current = vr[1]()
    logLine ("renderer set to: " + (renderers.current as string))

    local mtl = VRayMtl name:"P4_Teapot"
    mtl.diffuse = color 200 70 40
    mtl.reflection = color 160 160 160
    try (mtl.reflection_glossiness = 0.8) catch (logLine ("reflection_glossiness not set: " + getCurrentException()))
    local floorMtl = VRayMtl name:"P4_Floor"
    floorMtl.diffuse = color 140 140 140

    local tp = Teapot name:"P4_Teapot" radius:30 segs:12 pos:[0, 0, 0]
    tp.material = mtl
    local fl = Plane name:"P4_Floor" length:400 width:400 pos:[0, 0, 0]
    fl.material = floorMtl

    -- Plane light above the teapot, pointing down (-Z), hidden from the camera.
    local lt = VRayLight name:"P4_Light" pos:[60, -60, 160]
    lt.type = 0
    lt.size0 = 40
    lt.size1 = 40
    lt.multiplier = 20
    try (lt.invisible = true) catch (logLine ("invisible not set: " + getCurrentException()))

    local cam = Targetcamera name:"RenderCam" pos:[160, -220, 120] target:(Targetobject name:"RenderCam.Target" pos:[0, 0, 20])
    viewport.setCamera cam
    renderWidth = 640
    renderHeight = 360

    saveMaxFile scenePath quiet:true
    logLine ("saved scene: " + scenePath + " exists: " + ((doesFileExist scenePath) as string))
    if not (doesFileExist scenePath) do throw ("scene was not saved: " + scenePath)
)
