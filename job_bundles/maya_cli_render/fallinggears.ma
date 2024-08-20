//Maya ASCII 2023 scene
//Name: fallinggears.ma
//Last modified: Mon, Aug 19, 2024 06:28:28 PM
//Codeset: 1252
requires maya "2023";
requires -nodeType "polyGear" "modelingToolkit" "0.0.0.0";
requires "stereoCamera" "10.0";
requires "stereoCamera" "10.0";
currentUnit -l centimeter -a degree -t film;
fileInfo "application" "maya";
fileInfo "product" "Maya 2023";
fileInfo "version" "2023";
fileInfo "cutIdentifier" "202202161415-df43006fd3";
fileInfo "osv" "Windows 10 Enterprise v2009 (Build: 19045)";
fileInfo "UUID" "F0C77567-4069-A699-B095-DEB460F1D755";
createNode transform -s -n "persp";
	rename -uid "2ED16748-4DA5-8CB9-B713-2AB95C38258C";
	setAttr ".t" -type "double3" 2.6495225373093012 5.6474715141522562 9.1197163908291063 ;
	setAttr ".r" -type "double3" -18.338352729584766 16.199999999988574 0 ;
createNode camera -s -n "perspShape" -p "persp";
	rename -uid "EEC599E3-4EA7-4EE0-ACFB-85B0DFFDE6BF";
	setAttr -k off ".v";
	setAttr ".fl" 34.999999999999993;
	setAttr ".coi" 10.791357314716802;
	setAttr ".imn" -type "string" "persp";
	setAttr ".den" -type "string" "persp_depth";
	setAttr ".man" -type "string" "persp_mask";
	setAttr ".hc" -type "string" "viewSet -p %camera";
createNode transform -n "persp1";
	rename -uid "E87979F6-4260-9E6C-96C7-DBA0F9FBE5B3";
	setAttr ".v" no;
	setAttr ".t" -type "double3" -3.7426409959831979 17.324812305578998 27.321945580078406 ;
	setAttr ".r" -type "double3" -32.138352729639841 352.19999999998385 -4.0128206082566182e-16 ;
createNode camera -n "perspShape1" -p "persp1";
	rename -uid "EA7E56E9-4209-0BC2-D32A-EB9AA22A995F";
	setAttr -k off ".v";
	setAttr ".rnd" no;
	setAttr ".fl" 34.999999999999993;
	setAttr ".coi" 32.567548162688972;
	setAttr ".imn" -type "string" "persp1";
	setAttr ".den" -type "string" "persp1_depth";
	setAttr ".man" -type "string" "persp1_mask";
	setAttr ".hc" -type "string" "viewSet -p %camera";
createNode transform -s -n "top";
	rename -uid "E884829D-499B-DB28-FEA4-70B3F8A8F3D9";
	setAttr ".v" no;
	setAttr ".t" -type "double3" 0 1000.1 0 ;
	setAttr ".r" -type "double3" -90 0 0 ;
createNode camera -s -n "topShape" -p "top";
	rename -uid "D4EEC631-4E6A-C1C5-8A4B-DCA755490187";
	setAttr -k off ".v" no;
	setAttr ".rnd" no;
	setAttr ".coi" 1000.1;
	setAttr ".ow" 30;
	setAttr ".imn" -type "string" "top";
	setAttr ".den" -type "string" "top_depth";
	setAttr ".man" -type "string" "top_mask";
	setAttr ".hc" -type "string" "viewSet -t %camera";
	setAttr ".o" yes;
createNode transform -s -n "front";
	rename -uid "A7EF178B-4C97-0AFF-462B-A58450BC1B67";
	setAttr ".v" no;
	setAttr ".t" -type "double3" 0 0 1000.1 ;
createNode camera -s -n "frontShape" -p "front";
	rename -uid "F99DA551-462B-64E2-30CB-32ACD7CE97A8";
	setAttr -k off ".v" no;
	setAttr ".rnd" no;
	setAttr ".coi" 1000.1;
	setAttr ".ow" 30;
	setAttr ".imn" -type "string" "front";
	setAttr ".den" -type "string" "front_depth";
	setAttr ".man" -type "string" "front_mask";
	setAttr ".hc" -type "string" "viewSet -f %camera";
	setAttr ".o" yes;
createNode transform -s -n "side";
	rename -uid "93A97A0B-44CA-9D9F-3972-CBA5515DB757";
	setAttr ".v" no;
	setAttr ".t" -type "double3" 1000.1 0 0 ;
	setAttr ".r" -type "double3" 0 90 0 ;
createNode camera -s -n "sideShape" -p "side";
	rename -uid "233F7900-4A16-5ED2-0D30-97A5C441A736";
	setAttr -k off ".v";
	setAttr ".rnd" no;
	setAttr ".coi" 1000.1;
	setAttr ".ow" 30;
	setAttr ".imn" -type "string" "side";
	setAttr ".den" -type "string" "side_depth";
	setAttr ".man" -type "string" "side_mask";
	setAttr ".hc" -type "string" "viewSet -s %camera";
	setAttr ".o" yes;
createNode transform -n "pPlane1";
	rename -uid "E363E66F-448A-FA29-927C-E19459F1AE36";
	setAttr ".t" -type "double3" -1.9044522730017106 0 -4.3762156451835263 ;
	setAttr ".s" -type "double3" 20 20 20 ;
createNode mesh -n "pPlaneShape1" -p "pPlane1";
	rename -uid "00DA57FF-4754-A0CF-3966-F4A25722915F";
	setAttr -k off ".v";
	setAttr ".vir" yes;
	setAttr ".vif" yes;
	setAttr ".uvst[0].uvsn" -type "string" "map1";
	setAttr ".cuvs" -type "string" "map1";
	setAttr ".dcc" -type "string" "Ambient+Diffuse";
	setAttr ".covm[0]"  0 1 1;
	setAttr ".cdvm[0]"  0 1 1;
createNode transform -n "pointLight1";
	rename -uid "75860298-40ED-C223-4336-3481D888FA20";
	setAttr ".t" -type "double3" -4.9921904654207649 8.9339826114615022 7.6508866066242955 ;
createNode pointLight -n "pointLightShape1" -p "pointLight1";
	rename -uid "BA417AE6-40C9-0B05-C459-64B8012D476B";
	setAttr -k off ".v";
	setAttr ".urs" no;
	setAttr ".dms" yes;
	setAttr ".dr" 1557;
createNode transform -n "pointLight2";
	rename -uid "C4A71F3B-418A-2AF4-82D5-388B1FDAAA64";
	setAttr ".t" -type "double3" 10.010452828413641 6.3304809339896995 -8.3766524959522251 ;
createNode pointLight -n "pointLightShape2" -p "pointLight2";
	rename -uid "6FCC6086-465E-F09A-AA75-54AF578B3C3E";
	setAttr -k off ".v";
	setAttr ".urs" no;
	setAttr ".dms" yes;
	setAttr ".dr" 1372;
	setAttr ".us" no;
createNode transform -n "pGear1";
	rename -uid "23D952EE-45C7-F4D5-44A1-AFA38CE39F6F";
createNode mesh -n "pGearShape1" -p "pGear1";
	rename -uid "FA7F9B60-4719-2806-752B-9FB1B8BE5B24";
	setAttr -k off ".v";
	setAttr ".vir" yes;
	setAttr ".vif" yes;
	setAttr ".uvst[0].uvsn" -type "string" "map1";
	setAttr ".cuvs" -type "string" "map1";
	setAttr ".dcc" -type "string" "Ambient+Diffuse";
	setAttr ".covm[0]"  0 1 1;
	setAttr ".cdvm[0]"  0 1 1;
createNode transform -n "pGear2";
	rename -uid "AA3345E3-4CE3-E61C-48CF-8D83444BFFDE";
createNode mesh -n "pGearShape2" -p "pGear2";
	rename -uid "59107CC0-4023-DA98-5717-39870AFF5575";
	setAttr -k off ".v";
	setAttr ".vir" yes;
	setAttr ".vif" yes;
	setAttr ".uvst[0].uvsn" -type "string" "map1";
	setAttr ".cuvs" -type "string" "map1";
	setAttr ".dcc" -type "string" "Ambient+Diffuse";
	setAttr ".covm[0]"  0 1 1;
	setAttr ".cdvm[0]"  0 1 1;
createNode transform -n "pGear3";
	rename -uid "015B3B72-4D5E-1DCD-B578-0D887657D553";
createNode mesh -n "pGearShape3" -p "pGear3";
	rename -uid "2F57B8D2-4866-82E9-6C89-77B8B9D317F2";
	setAttr -k off ".v";
	setAttr ".vir" yes;
	setAttr ".vif" yes;
	setAttr ".uvst[0].uvsn" -type "string" "map1";
	setAttr ".cuvs" -type "string" "map1";
	setAttr ".dcc" -type "string" "Ambient+Diffuse";
	setAttr ".covm[0]"  0 1 1;
	setAttr ".cdvm[0]"  0 1 1;
createNode transform -n "pGear4";
	rename -uid "21D69B36-4563-3BAD-154F-B0ADB200CCAA";
createNode mesh -n "pGearShape4" -p "pGear4";
	rename -uid "C8B91634-4EAC-D178-5CBA-5E970B6BE8A7";
	setAttr -k off ".v";
	setAttr ".vir" yes;
	setAttr ".vif" yes;
	setAttr ".uvst[0].uvsn" -type "string" "map1";
	setAttr ".cuvs" -type "string" "map1";
	setAttr ".dcc" -type "string" "Ambient+Diffuse";
	setAttr ".covm[0]"  0 1 1;
	setAttr ".cdvm[0]"  0 1 1;
createNode lightLinker -s -n "lightLinker1";
	rename -uid "A9CAC521-462F-7ED0-0AA3-0492995BF432";
	setAttr -s 2 ".lnk";
	setAttr -s 2 ".slnk";
createNode shapeEditorManager -n "shapeEditorManager";
	rename -uid "B97E73F6-40C5-5BF5-3CEE-27A0ADD979F6";
createNode poseInterpolatorManager -n "poseInterpolatorManager";
	rename -uid "CD5D9C26-4B8E-A271-B2C8-9ABD92282FF3";
createNode displayLayerManager -n "layerManager";
	rename -uid "B56A4F08-4F85-EFF8-8711-F5BEAF4DAA28";
createNode displayLayer -n "defaultLayer";
	rename -uid "96F6E540-4984-D1EF-0CA6-8880EA54B932";
createNode renderLayerManager -n "renderLayerManager";
	rename -uid "2EAA8B0D-4C34-CF0A-A97D-DA82A951685E";
createNode renderLayer -n "defaultRenderLayer";
	rename -uid "48C8CBE4-4E86-A3AB-73C9-30A940E90E19";
	setAttr ".g" yes;
createNode polyPlane -n "polyPlane1";
	rename -uid "64CDEDB6-4C10-F01A-374F-F6835A55DFC8";
	setAttr ".cuv" 2;
createNode script -n "uiConfigurationScriptNode";
	rename -uid "723EB7C0-44AD-EAB9-7D59-2C956D76F169";
	setAttr ".b" -type "string" (
		"// Maya Mel UI Configuration File.\n//\n//  This script is machine generated.  Edit at your own risk.\n//\n//\n\nglobal string $gMainPane;\nif (`paneLayout -exists $gMainPane`) {\n\n\tglobal int $gUseScenePanelConfig;\n\tint    $useSceneConfig = $gUseScenePanelConfig;\n\tint    $nodeEditorPanelVisible = stringArrayContains(\"nodeEditorPanel1\", `getPanel -vis`);\n\tint    $nodeEditorWorkspaceControlOpen = (`workspaceControl -exists nodeEditorPanel1Window` && `workspaceControl -q -visible nodeEditorPanel1Window`);\n\tint    $menusOkayInPanels = `optionVar -q allowMenusInPanels`;\n\tint    $nVisPanes = `paneLayout -q -nvp $gMainPane`;\n\tint    $nPanes = 0;\n\tstring $editorName;\n\tstring $panelName;\n\tstring $itemFilterName;\n\tstring $panelConfig;\n\n\t//\n\t//  get current state of the UI\n\t//\n\tsceneUIReplacement -update $gMainPane;\n\n\t$panelName = `sceneUIReplacement -getNextPanel \"modelPanel\" (localizedPanelLabel(\"Top View\")) `;\n\tif (\"\" != $panelName) {\n\t\t$label = `panel -q -label $panelName`;\n\t\tmodelPanel -edit -l (localizedPanelLabel(\"Top View\")) -mbv $menusOkayInPanels  $panelName;\n"
		+ "\t\t$editorName = $panelName;\n        modelEditor -e \n            -camera \"|top\" \n            -useInteractiveMode 0\n            -displayLights \"default\" \n            -displayAppearance \"smoothShaded\" \n            -activeOnly 0\n            -ignorePanZoom 0\n            -wireframeOnShaded 0\n            -headsUpDisplay 1\n            -holdOuts 1\n            -selectionHiliteDisplay 1\n            -useDefaultMaterial 0\n            -bufferMode \"double\" \n            -twoSidedLighting 0\n            -backfaceCulling 0\n            -xray 0\n            -jointXray 0\n            -activeComponentsXray 0\n            -displayTextures 0\n            -smoothWireframe 0\n            -lineWidth 1\n            -textureAnisotropic 0\n            -textureHilight 1\n            -textureSampling 2\n            -textureDisplay \"modulate\" \n            -textureMaxSize 32768\n            -fogging 0\n            -fogSource \"fragment\" \n            -fogMode \"linear\" \n            -fogStart 0\n            -fogEnd 100\n            -fogDensity 0.1\n            -fogColor 0.5 0.5 0.5 1 \n"
		+ "            -depthOfFieldPreview 1\n            -maxConstantTransparency 1\n            -rendererName \"vp2Renderer\" \n            -objectFilterShowInHUD 1\n            -isFiltered 0\n            -colorResolution 256 256 \n            -bumpResolution 512 512 \n            -textureCompression 0\n            -transparencyAlgorithm \"frontAndBackCull\" \n            -transpInShadows 0\n            -cullingOverride \"none\" \n            -lowQualityLighting 0\n            -maximumNumHardwareLights 1\n            -occlusionCulling 0\n            -shadingModel 0\n            -useBaseRenderer 0\n            -useReducedRenderer 0\n            -smallObjectCulling 0\n            -smallObjectThreshold -1 \n            -interactiveDisableShadows 0\n            -interactiveBackFaceCull 0\n            -sortTransparent 1\n            -controllers 1\n            -nurbsCurves 1\n            -nurbsSurfaces 1\n            -polymeshes 1\n            -subdivSurfaces 1\n            -planes 1\n            -lights 1\n            -cameras 1\n            -controlVertices 1\n"
		+ "            -hulls 1\n            -grid 1\n            -imagePlane 1\n            -joints 1\n            -ikHandles 1\n            -deformers 1\n            -dynamics 1\n            -particleInstancers 1\n            -fluids 1\n            -hairSystems 1\n            -follicles 1\n            -nCloths 1\n            -nParticles 1\n            -nRigids 1\n            -dynamicConstraints 1\n            -locators 1\n            -manipulators 1\n            -pluginShapes 1\n            -dimensions 1\n            -handles 1\n            -pivots 1\n            -textures 1\n            -strokes 1\n            -motionTrails 1\n            -clipGhosts 1\n            -greasePencils 0\n            -shadows 0\n            -captureSequenceNumber -1\n            -width 1\n            -height 1\n            -sceneRenderFilter 0\n            $editorName;\n        modelEditor -e -viewSelected 0 $editorName;\n        modelEditor -e \n            -pluginObjects \"gpuCacheDisplayFilter\" 1 \n            $editorName;\n\t\tif (!$useSceneConfig) {\n\t\t\tpanel -e -l $label $panelName;\n"
		+ "\t\t}\n\t}\n\n\n\t$panelName = `sceneUIReplacement -getNextPanel \"modelPanel\" (localizedPanelLabel(\"Side View\")) `;\n\tif (\"\" != $panelName) {\n\t\t$label = `panel -q -label $panelName`;\n\t\tmodelPanel -edit -l (localizedPanelLabel(\"Side View\")) -mbv $menusOkayInPanels  $panelName;\n\t\t$editorName = $panelName;\n        modelEditor -e \n            -camera \"|side\" \n            -useInteractiveMode 0\n            -displayLights \"default\" \n            -displayAppearance \"smoothShaded\" \n            -activeOnly 0\n            -ignorePanZoom 0\n            -wireframeOnShaded 0\n            -headsUpDisplay 1\n            -holdOuts 1\n            -selectionHiliteDisplay 1\n            -useDefaultMaterial 0\n            -bufferMode \"double\" \n            -twoSidedLighting 0\n            -backfaceCulling 0\n            -xray 0\n            -jointXray 0\n            -activeComponentsXray 0\n            -displayTextures 0\n            -smoothWireframe 0\n            -lineWidth 1\n            -textureAnisotropic 0\n            -textureHilight 1\n            -textureSampling 2\n"
		+ "            -textureDisplay \"modulate\" \n            -textureMaxSize 32768\n            -fogging 0\n            -fogSource \"fragment\" \n            -fogMode \"linear\" \n            -fogStart 0\n            -fogEnd 100\n            -fogDensity 0.1\n            -fogColor 0.5 0.5 0.5 1 \n            -depthOfFieldPreview 1\n            -maxConstantTransparency 1\n            -rendererName \"vp2Renderer\" \n            -objectFilterShowInHUD 1\n            -isFiltered 0\n            -colorResolution 256 256 \n            -bumpResolution 512 512 \n            -textureCompression 0\n            -transparencyAlgorithm \"frontAndBackCull\" \n            -transpInShadows 0\n            -cullingOverride \"none\" \n            -lowQualityLighting 0\n            -maximumNumHardwareLights 1\n            -occlusionCulling 0\n            -shadingModel 0\n            -useBaseRenderer 0\n            -useReducedRenderer 0\n            -smallObjectCulling 0\n            -smallObjectThreshold -1 \n            -interactiveDisableShadows 0\n            -interactiveBackFaceCull 0\n"
		+ "            -sortTransparent 1\n            -controllers 1\n            -nurbsCurves 1\n            -nurbsSurfaces 1\n            -polymeshes 1\n            -subdivSurfaces 1\n            -planes 1\n            -lights 1\n            -cameras 1\n            -controlVertices 1\n            -hulls 1\n            -grid 1\n            -imagePlane 1\n            -joints 1\n            -ikHandles 1\n            -deformers 1\n            -dynamics 1\n            -particleInstancers 1\n            -fluids 1\n            -hairSystems 1\n            -follicles 1\n            -nCloths 1\n            -nParticles 1\n            -nRigids 1\n            -dynamicConstraints 1\n            -locators 1\n            -manipulators 1\n            -pluginShapes 1\n            -dimensions 1\n            -handles 1\n            -pivots 1\n            -textures 1\n            -strokes 1\n            -motionTrails 1\n            -clipGhosts 1\n            -greasePencils 0\n            -shadows 0\n            -captureSequenceNumber -1\n            -width 1\n            -height 1\n"
		+ "            -sceneRenderFilter 0\n            $editorName;\n        modelEditor -e -viewSelected 0 $editorName;\n        modelEditor -e \n            -pluginObjects \"gpuCacheDisplayFilter\" 1 \n            $editorName;\n\t\tif (!$useSceneConfig) {\n\t\t\tpanel -e -l $label $panelName;\n\t\t}\n\t}\n\n\n\t$panelName = `sceneUIReplacement -getNextPanel \"modelPanel\" (localizedPanelLabel(\"Front View\")) `;\n\tif (\"\" != $panelName) {\n\t\t$label = `panel -q -label $panelName`;\n\t\tmodelPanel -edit -l (localizedPanelLabel(\"Front View\")) -mbv $menusOkayInPanels  $panelName;\n\t\t$editorName = $panelName;\n        modelEditor -e \n            -camera \"|front\" \n            -useInteractiveMode 0\n            -displayLights \"default\" \n            -displayAppearance \"smoothShaded\" \n            -activeOnly 0\n            -ignorePanZoom 0\n            -wireframeOnShaded 0\n            -headsUpDisplay 1\n            -holdOuts 1\n            -selectionHiliteDisplay 1\n            -useDefaultMaterial 0\n            -bufferMode \"double\" \n            -twoSidedLighting 0\n            -backfaceCulling 0\n"
		+ "            -xray 0\n            -jointXray 0\n            -activeComponentsXray 0\n            -displayTextures 0\n            -smoothWireframe 0\n            -lineWidth 1\n            -textureAnisotropic 0\n            -textureHilight 1\n            -textureSampling 2\n            -textureDisplay \"modulate\" \n            -textureMaxSize 32768\n            -fogging 0\n            -fogSource \"fragment\" \n            -fogMode \"linear\" \n            -fogStart 0\n            -fogEnd 100\n            -fogDensity 0.1\n            -fogColor 0.5 0.5 0.5 1 \n            -depthOfFieldPreview 1\n            -maxConstantTransparency 1\n            -rendererName \"vp2Renderer\" \n            -objectFilterShowInHUD 1\n            -isFiltered 0\n            -colorResolution 256 256 \n            -bumpResolution 512 512 \n            -textureCompression 0\n            -transparencyAlgorithm \"frontAndBackCull\" \n            -transpInShadows 0\n            -cullingOverride \"none\" \n            -lowQualityLighting 0\n            -maximumNumHardwareLights 1\n            -occlusionCulling 0\n"
		+ "            -shadingModel 0\n            -useBaseRenderer 0\n            -useReducedRenderer 0\n            -smallObjectCulling 0\n            -smallObjectThreshold -1 \n            -interactiveDisableShadows 0\n            -interactiveBackFaceCull 0\n            -sortTransparent 1\n            -controllers 1\n            -nurbsCurves 1\n            -nurbsSurfaces 1\n            -polymeshes 1\n            -subdivSurfaces 1\n            -planes 1\n            -lights 1\n            -cameras 1\n            -controlVertices 1\n            -hulls 1\n            -grid 1\n            -imagePlane 1\n            -joints 1\n            -ikHandles 1\n            -deformers 1\n            -dynamics 1\n            -particleInstancers 1\n            -fluids 1\n            -hairSystems 1\n            -follicles 1\n            -nCloths 1\n            -nParticles 1\n            -nRigids 1\n            -dynamicConstraints 1\n            -locators 1\n            -manipulators 1\n            -pluginShapes 1\n            -dimensions 1\n            -handles 1\n            -pivots 1\n"
		+ "            -textures 1\n            -strokes 1\n            -motionTrails 1\n            -clipGhosts 1\n            -greasePencils 0\n            -shadows 0\n            -captureSequenceNumber -1\n            -width 1\n            -height 1\n            -sceneRenderFilter 0\n            $editorName;\n        modelEditor -e -viewSelected 0 $editorName;\n        modelEditor -e \n            -pluginObjects \"gpuCacheDisplayFilter\" 1 \n            $editorName;\n\t\tif (!$useSceneConfig) {\n\t\t\tpanel -e -l $label $panelName;\n\t\t}\n\t}\n\n\n\t$panelName = `sceneUIReplacement -getNextPanel \"modelPanel\" (localizedPanelLabel(\"Persp View\")) `;\n\tif (\"\" != $panelName) {\n\t\t$label = `panel -q -label $panelName`;\n\t\tmodelPanel -edit -l (localizedPanelLabel(\"Persp View\")) -mbv $menusOkayInPanels  $panelName;\n\t\t$editorName = $panelName;\n        modelEditor -e \n            -camera \"|persp\" \n            -useInteractiveMode 0\n            -displayLights \"default\" \n            -displayAppearance \"smoothShaded\" \n            -activeOnly 0\n            -ignorePanZoom 0\n"
		+ "            -wireframeOnShaded 0\n            -headsUpDisplay 1\n            -holdOuts 1\n            -selectionHiliteDisplay 1\n            -useDefaultMaterial 0\n            -bufferMode \"double\" \n            -twoSidedLighting 0\n            -backfaceCulling 0\n            -xray 0\n            -jointXray 0\n            -activeComponentsXray 0\n            -displayTextures 0\n            -smoothWireframe 0\n            -lineWidth 1\n            -textureAnisotropic 0\n            -textureHilight 1\n            -textureSampling 2\n            -textureDisplay \"modulate\" \n            -textureMaxSize 32768\n            -fogging 0\n            -fogSource \"fragment\" \n            -fogMode \"linear\" \n            -fogStart 0\n            -fogEnd 100\n            -fogDensity 0.1\n            -fogColor 0.5 0.5 0.5 1 \n            -depthOfFieldPreview 1\n            -maxConstantTransparency 1\n            -rendererName \"vp2Renderer\" \n            -objectFilterShowInHUD 1\n            -isFiltered 0\n            -colorResolution 256 256 \n            -bumpResolution 512 512 \n"
		+ "            -textureCompression 0\n            -transparencyAlgorithm \"frontAndBackCull\" \n            -transpInShadows 0\n            -cullingOverride \"none\" \n            -lowQualityLighting 0\n            -maximumNumHardwareLights 1\n            -occlusionCulling 0\n            -shadingModel 0\n            -useBaseRenderer 0\n            -useReducedRenderer 0\n            -smallObjectCulling 0\n            -smallObjectThreshold -1 \n            -interactiveDisableShadows 0\n            -interactiveBackFaceCull 0\n            -sortTransparent 1\n            -controllers 1\n            -nurbsCurves 1\n            -nurbsSurfaces 1\n            -polymeshes 1\n            -subdivSurfaces 1\n            -planes 1\n            -lights 1\n            -cameras 1\n            -controlVertices 1\n            -hulls 1\n            -grid 1\n            -imagePlane 1\n            -joints 1\n            -ikHandles 1\n            -deformers 1\n            -dynamics 1\n            -particleInstancers 1\n            -fluids 1\n            -hairSystems 1\n            -follicles 1\n"
		+ "            -nCloths 1\n            -nParticles 1\n            -nRigids 1\n            -dynamicConstraints 1\n            -locators 1\n            -manipulators 1\n            -pluginShapes 1\n            -dimensions 1\n            -handles 1\n            -pivots 1\n            -textures 1\n            -strokes 1\n            -motionTrails 1\n            -clipGhosts 1\n            -greasePencils 0\n            -shadows 0\n            -captureSequenceNumber -1\n            -width 1286\n            -height 740\n            -sceneRenderFilter 0\n            $editorName;\n        modelEditor -e -viewSelected 0 $editorName;\n        modelEditor -e \n            -pluginObjects \"gpuCacheDisplayFilter\" 1 \n            $editorName;\n\t\tif (!$useSceneConfig) {\n\t\t\tpanel -e -l $label $panelName;\n\t\t}\n\t}\n\n\n\t$panelName = `sceneUIReplacement -getNextPanel \"outlinerPanel\" (localizedPanelLabel(\"ToggledOutliner\")) `;\n\tif (\"\" != $panelName) {\n\t\t$label = `panel -q -label $panelName`;\n\t\toutlinerPanel -edit -l (localizedPanelLabel(\"ToggledOutliner\")) -mbv $menusOkayInPanels  $panelName;\n"
		+ "\t\t$editorName = $panelName;\n        outlinerEditor -e \n            -docTag \"isolOutln_fromSeln\" \n            -showShapes 0\n            -showAssignedMaterials 1\n            -showTimeEditor 1\n            -showReferenceNodes 1\n            -showReferenceMembers 1\n            -showAttributes 0\n            -showConnected 0\n            -showAnimCurvesOnly 0\n            -showMuteInfo 0\n            -organizeByLayer 1\n            -organizeByClip 1\n            -showAnimLayerWeight 1\n            -autoExpandLayers 1\n            -autoExpand 0\n            -showDagOnly 1\n            -showAssets 1\n            -showContainedOnly 1\n            -showPublishedAsConnected 0\n            -showParentContainers 0\n            -showContainerContents 1\n            -ignoreDagHierarchy 0\n            -expandConnections 0\n            -showUpstreamCurves 1\n            -showUnitlessCurves 1\n            -showCompounds 1\n            -showLeafs 1\n            -showNumericAttrsOnly 0\n            -highlightActive 1\n            -autoSelectNewObjects 0\n"
		+ "            -doNotSelectNewObjects 0\n            -dropIsParent 1\n            -transmitFilters 0\n            -setFilter \"defaultSetFilter\" \n            -showSetMembers 1\n            -allowMultiSelection 1\n            -alwaysToggleSelect 0\n            -directSelect 0\n            -isSet 0\n            -isSetMember 0\n            -displayMode \"DAG\" \n            -expandObjects 0\n            -setsIgnoreFilters 1\n            -containersIgnoreFilters 0\n            -editAttrName 0\n            -showAttrValues 0\n            -highlightSecondary 0\n            -showUVAttrsOnly 0\n            -showTextureNodesOnly 0\n            -attrAlphaOrder \"default\" \n            -animLayerFilterOptions \"allAffecting\" \n            -sortOrder \"none\" \n            -longNames 0\n            -niceNames 1\n            -showNamespace 1\n            -showPinIcons 0\n            -mapMotionTrails 0\n            -ignoreHiddenAttribute 0\n            -ignoreOutlinerColor 0\n            -renderFilterVisible 0\n            -renderFilterIndex 0\n            -selectionOrder \"chronological\" \n"
		+ "            -expandAttribute 0\n            $editorName;\n\t\tif (!$useSceneConfig) {\n\t\t\tpanel -e -l $label $panelName;\n\t\t}\n\t}\n\n\n\t$panelName = `sceneUIReplacement -getNextPanel \"outlinerPanel\" (localizedPanelLabel(\"Outliner\")) `;\n\tif (\"\" != $panelName) {\n\t\t$label = `panel -q -label $panelName`;\n\t\toutlinerPanel -edit -l (localizedPanelLabel(\"Outliner\")) -mbv $menusOkayInPanels  $panelName;\n\t\t$editorName = $panelName;\n        outlinerEditor -e \n            -showShapes 0\n            -showAssignedMaterials 0\n            -showTimeEditor 1\n            -showReferenceNodes 0\n            -showReferenceMembers 0\n            -showAttributes 0\n            -showConnected 0\n            -showAnimCurvesOnly 0\n            -showMuteInfo 0\n            -organizeByLayer 1\n            -organizeByClip 1\n            -showAnimLayerWeight 1\n            -autoExpandLayers 1\n            -autoExpand 0\n            -showDagOnly 1\n            -showAssets 1\n            -showContainedOnly 1\n            -showPublishedAsConnected 0\n            -showParentContainers 0\n"
		+ "            -showContainerContents 1\n            -ignoreDagHierarchy 0\n            -expandConnections 0\n            -showUpstreamCurves 1\n            -showUnitlessCurves 1\n            -showCompounds 1\n            -showLeafs 1\n            -showNumericAttrsOnly 0\n            -highlightActive 1\n            -autoSelectNewObjects 0\n            -doNotSelectNewObjects 0\n            -dropIsParent 1\n            -transmitFilters 0\n            -setFilter \"defaultSetFilter\" \n            -showSetMembers 1\n            -allowMultiSelection 1\n            -alwaysToggleSelect 0\n            -directSelect 0\n            -displayMode \"DAG\" \n            -expandObjects 0\n            -setsIgnoreFilters 1\n            -containersIgnoreFilters 0\n            -editAttrName 0\n            -showAttrValues 0\n            -highlightSecondary 0\n            -showUVAttrsOnly 0\n            -showTextureNodesOnly 0\n            -attrAlphaOrder \"default\" \n            -animLayerFilterOptions \"allAffecting\" \n            -sortOrder \"none\" \n            -longNames 0\n"
		+ "            -niceNames 1\n            -showNamespace 1\n            -showPinIcons 0\n            -mapMotionTrails 0\n            -ignoreHiddenAttribute 0\n            -ignoreOutlinerColor 0\n            -renderFilterVisible 0\n            $editorName;\n\t\tif (!$useSceneConfig) {\n\t\t\tpanel -e -l $label $panelName;\n\t\t}\n\t}\n\n\n\t$panelName = `sceneUIReplacement -getNextScriptedPanel \"graphEditor\" (localizedPanelLabel(\"Graph Editor\")) `;\n\tif (\"\" != $panelName) {\n\t\t$label = `panel -q -label $panelName`;\n\t\tscriptedPanel -edit -l (localizedPanelLabel(\"Graph Editor\")) -mbv $menusOkayInPanels  $panelName;\n\n\t\t\t$editorName = ($panelName+\"OutlineEd\");\n            outlinerEditor -e \n                -showShapes 1\n                -showAssignedMaterials 0\n                -showTimeEditor 1\n                -showReferenceNodes 0\n                -showReferenceMembers 0\n                -showAttributes 1\n                -showConnected 1\n                -showAnimCurvesOnly 1\n                -showMuteInfo 0\n                -organizeByLayer 1\n                -organizeByClip 1\n"
		+ "                -showAnimLayerWeight 1\n                -autoExpandLayers 1\n                -autoExpand 1\n                -showDagOnly 0\n                -showAssets 1\n                -showContainedOnly 0\n                -showPublishedAsConnected 0\n                -showParentContainers 0\n                -showContainerContents 0\n                -ignoreDagHierarchy 0\n                -expandConnections 1\n                -showUpstreamCurves 1\n                -showUnitlessCurves 1\n                -showCompounds 0\n                -showLeafs 1\n                -showNumericAttrsOnly 1\n                -highlightActive 0\n                -autoSelectNewObjects 1\n                -doNotSelectNewObjects 0\n                -dropIsParent 1\n                -transmitFilters 1\n                -setFilter \"0\" \n                -showSetMembers 0\n                -allowMultiSelection 1\n                -alwaysToggleSelect 0\n                -directSelect 0\n                -displayMode \"DAG\" \n                -expandObjects 0\n                -setsIgnoreFilters 1\n"
		+ "                -containersIgnoreFilters 0\n                -editAttrName 0\n                -showAttrValues 0\n                -highlightSecondary 0\n                -showUVAttrsOnly 0\n                -showTextureNodesOnly 0\n                -attrAlphaOrder \"default\" \n                -animLayerFilterOptions \"allAffecting\" \n                -sortOrder \"none\" \n                -longNames 0\n                -niceNames 1\n                -showNamespace 1\n                -showPinIcons 1\n                -mapMotionTrails 1\n                -ignoreHiddenAttribute 0\n                -ignoreOutlinerColor 0\n                -renderFilterVisible 0\n                $editorName;\n\n\t\t\t$editorName = ($panelName+\"GraphEd\");\n            animCurveEditor -e \n                -displayValues 0\n                -snapTime \"integer\" \n                -snapValue \"none\" \n                -showPlayRangeShades \"on\" \n                -lockPlayRangeShades \"off\" \n                -smoothness \"fine\" \n                -resultSamples 1\n                -resultScreenSamples 0\n"
		+ "                -resultUpdate \"delayed\" \n                -showUpstreamCurves 1\n                -keyMinScale 1\n                -stackedCurvesMin -1\n                -stackedCurvesMax 1\n                -stackedCurvesSpace 0.2\n                -preSelectionHighlight 0\n                -constrainDrag 0\n                -valueLinesToggle 1\n                -outliner \"graphEditor1OutlineEd\" \n                -highlightAffectedCurves 0\n                $editorName;\n\t\tif (!$useSceneConfig) {\n\t\t\tpanel -e -l $label $panelName;\n\t\t}\n\t}\n\n\n\t$panelName = `sceneUIReplacement -getNextScriptedPanel \"dopeSheetPanel\" (localizedPanelLabel(\"Dope Sheet\")) `;\n\tif (\"\" != $panelName) {\n\t\t$label = `panel -q -label $panelName`;\n\t\tscriptedPanel -edit -l (localizedPanelLabel(\"Dope Sheet\")) -mbv $menusOkayInPanels  $panelName;\n\n\t\t\t$editorName = ($panelName+\"OutlineEd\");\n            outlinerEditor -e \n                -showShapes 1\n                -showAssignedMaterials 0\n                -showTimeEditor 1\n                -showReferenceNodes 0\n                -showReferenceMembers 0\n"
		+ "                -showAttributes 1\n                -showConnected 1\n                -showAnimCurvesOnly 1\n                -showMuteInfo 0\n                -organizeByLayer 1\n                -organizeByClip 1\n                -showAnimLayerWeight 1\n                -autoExpandLayers 1\n                -autoExpand 0\n                -showDagOnly 0\n                -showAssets 1\n                -showContainedOnly 0\n                -showPublishedAsConnected 0\n                -showParentContainers 0\n                -showContainerContents 0\n                -ignoreDagHierarchy 0\n                -expandConnections 1\n                -showUpstreamCurves 1\n                -showUnitlessCurves 0\n                -showCompounds 1\n                -showLeafs 1\n                -showNumericAttrsOnly 1\n                -highlightActive 0\n                -autoSelectNewObjects 0\n                -doNotSelectNewObjects 1\n                -dropIsParent 1\n                -transmitFilters 0\n                -setFilter \"0\" \n                -showSetMembers 0\n"
		+ "                -allowMultiSelection 1\n                -alwaysToggleSelect 0\n                -directSelect 0\n                -displayMode \"DAG\" \n                -expandObjects 0\n                -setsIgnoreFilters 1\n                -containersIgnoreFilters 0\n                -editAttrName 0\n                -showAttrValues 0\n                -highlightSecondary 0\n                -showUVAttrsOnly 0\n                -showTextureNodesOnly 0\n                -attrAlphaOrder \"default\" \n                -animLayerFilterOptions \"allAffecting\" \n                -sortOrder \"none\" \n                -longNames 0\n                -niceNames 1\n                -showNamespace 1\n                -showPinIcons 0\n                -mapMotionTrails 1\n                -ignoreHiddenAttribute 0\n                -ignoreOutlinerColor 0\n                -renderFilterVisible 0\n                $editorName;\n\n\t\t\t$editorName = ($panelName+\"DopeSheetEd\");\n            dopeSheetEditor -e \n                -displayValues 0\n                -snapTime \"integer\" \n"
		+ "                -snapValue \"none\" \n                -outliner \"dopeSheetPanel1OutlineEd\" \n                -showSummary 1\n                -showScene 0\n                -hierarchyBelow 0\n                -showTicks 1\n                -selectionWindow 0 0 0 0 \n                $editorName;\n\t\tif (!$useSceneConfig) {\n\t\t\tpanel -e -l $label $panelName;\n\t\t}\n\t}\n\n\n\t$panelName = `sceneUIReplacement -getNextScriptedPanel \"timeEditorPanel\" (localizedPanelLabel(\"Time Editor\")) `;\n\tif (\"\" != $panelName) {\n\t\t$label = `panel -q -label $panelName`;\n\t\tscriptedPanel -edit -l (localizedPanelLabel(\"Time Editor\")) -mbv $menusOkayInPanels  $panelName;\n\t\tif (!$useSceneConfig) {\n\t\t\tpanel -e -l $label $panelName;\n\t\t}\n\t}\n\n\n\t$panelName = `sceneUIReplacement -getNextScriptedPanel \"clipEditorPanel\" (localizedPanelLabel(\"Trax Editor\")) `;\n\tif (\"\" != $panelName) {\n\t\t$label = `panel -q -label $panelName`;\n\t\tscriptedPanel -edit -l (localizedPanelLabel(\"Trax Editor\")) -mbv $menusOkayInPanels  $panelName;\n\n\t\t\t$editorName = clipEditorNameFromPanel($panelName);\n"
		+ "            clipEditor -e \n                -displayValues 0\n                -snapTime \"none\" \n                -snapValue \"none\" \n                -initialized 0\n                -manageSequencer 0 \n                $editorName;\n\t\tif (!$useSceneConfig) {\n\t\t\tpanel -e -l $label $panelName;\n\t\t}\n\t}\n\n\n\t$panelName = `sceneUIReplacement -getNextScriptedPanel \"sequenceEditorPanel\" (localizedPanelLabel(\"Camera Sequencer\")) `;\n\tif (\"\" != $panelName) {\n\t\t$label = `panel -q -label $panelName`;\n\t\tscriptedPanel -edit -l (localizedPanelLabel(\"Camera Sequencer\")) -mbv $menusOkayInPanels  $panelName;\n\n\t\t\t$editorName = sequenceEditorNameFromPanel($panelName);\n            clipEditor -e \n                -displayValues 0\n                -snapTime \"none\" \n                -snapValue \"none\" \n                -initialized 0\n                -manageSequencer 1 \n                $editorName;\n\t\tif (!$useSceneConfig) {\n\t\t\tpanel -e -l $label $panelName;\n\t\t}\n\t}\n\n\n\t$panelName = `sceneUIReplacement -getNextScriptedPanel \"hyperGraphPanel\" (localizedPanelLabel(\"Hypergraph Hierarchy\")) `;\n"
		+ "\tif (\"\" != $panelName) {\n\t\t$label = `panel -q -label $panelName`;\n\t\tscriptedPanel -edit -l (localizedPanelLabel(\"Hypergraph Hierarchy\")) -mbv $menusOkayInPanels  $panelName;\n\n\t\t\t$editorName = ($panelName+\"HyperGraphEd\");\n            hyperGraph -e \n                -graphLayoutStyle \"hierarchicalLayout\" \n                -orientation \"horiz\" \n                -mergeConnections 0\n                -zoom 1\n                -animateTransition 0\n                -showRelationships 1\n                -showShapes 0\n                -showDeformers 0\n                -showExpressions 0\n                -showConstraints 0\n                -showConnectionFromSelected 0\n                -showConnectionToSelected 0\n                -showConstraintLabels 0\n                -showUnderworld 0\n                -showInvisible 0\n                -transitionFrames 1\n                -opaqueContainers 0\n                -freeform 0\n                -imagePosition 0 0 \n                -imageScale 1\n                -imageEnabled 0\n                -graphType \"DAG\" \n"
		+ "                -heatMapDisplay 0\n                -updateSelection 1\n                -updateNodeAdded 1\n                -useDrawOverrideColor 0\n                -limitGraphTraversal -1\n                -range 0 0 \n                -iconSize \"smallIcons\" \n                -showCachedConnections 0\n                $editorName;\n\t\tif (!$useSceneConfig) {\n\t\t\tpanel -e -l $label $panelName;\n\t\t}\n\t}\n\n\n\t$panelName = `sceneUIReplacement -getNextScriptedPanel \"hyperShadePanel\" (localizedPanelLabel(\"Hypershade\")) `;\n\tif (\"\" != $panelName) {\n\t\t$label = `panel -q -label $panelName`;\n\t\tscriptedPanel -edit -l (localizedPanelLabel(\"Hypershade\")) -mbv $menusOkayInPanels  $panelName;\n\t\tif (!$useSceneConfig) {\n\t\t\tpanel -e -l $label $panelName;\n\t\t}\n\t}\n\n\n\t$panelName = `sceneUIReplacement -getNextScriptedPanel \"visorPanel\" (localizedPanelLabel(\"Visor\")) `;\n\tif (\"\" != $panelName) {\n\t\t$label = `panel -q -label $panelName`;\n\t\tscriptedPanel -edit -l (localizedPanelLabel(\"Visor\")) -mbv $menusOkayInPanels  $panelName;\n\t\tif (!$useSceneConfig) {\n"
		+ "\t\t\tpanel -e -l $label $panelName;\n\t\t}\n\t}\n\n\n\t$panelName = `sceneUIReplacement -getNextScriptedPanel \"nodeEditorPanel\" (localizedPanelLabel(\"Node Editor\")) `;\n\tif ($nodeEditorPanelVisible || $nodeEditorWorkspaceControlOpen) {\n\t\tif (\"\" == $panelName) {\n\t\t\tif ($useSceneConfig) {\n\t\t\t\t$panelName = `scriptedPanel -unParent  -type \"nodeEditorPanel\" -l (localizedPanelLabel(\"Node Editor\")) -mbv $menusOkayInPanels `;\n\n\t\t\t$editorName = ($panelName+\"NodeEditorEd\");\n            nodeEditor -e \n                -allAttributes 0\n                -allNodes 0\n                -autoSizeNodes 1\n                -consistentNameSize 1\n                -createNodeCommand \"nodeEdCreateNodeCommand\" \n                -connectNodeOnCreation 0\n                -connectOnDrop 0\n                -copyConnectionsOnPaste 0\n                -connectionStyle \"bezier\" \n                -defaultPinnedState 0\n                -additiveGraphingMode 0\n                -connectedGraphingMode 1\n                -settingsChangedCallback \"nodeEdSyncControls\" \n                -traversalDepthLimit -1\n"
		+ "                -keyPressCommand \"nodeEdKeyPressCommand\" \n                -nodeTitleMode \"name\" \n                -gridSnap 0\n                -gridVisibility 1\n                -crosshairOnEdgeDragging 0\n                -popupMenuScript \"nodeEdBuildPanelMenus\" \n                -showNamespace 1\n                -showShapes 1\n                -showSGShapes 0\n                -showTransforms 1\n                -useAssets 1\n                -syncedSelection 1\n                -extendToShapes 1\n                -showUnitConversions 0\n                -editorMode \"default\" \n                -hasWatchpoint 0\n                $editorName;\n\t\t\t}\n\t\t} else {\n\t\t\t$label = `panel -q -label $panelName`;\n\t\t\tscriptedPanel -edit -l (localizedPanelLabel(\"Node Editor\")) -mbv $menusOkayInPanels  $panelName;\n\n\t\t\t$editorName = ($panelName+\"NodeEditorEd\");\n            nodeEditor -e \n                -allAttributes 0\n                -allNodes 0\n                -autoSizeNodes 1\n                -consistentNameSize 1\n                -createNodeCommand \"nodeEdCreateNodeCommand\" \n"
		+ "                -connectNodeOnCreation 0\n                -connectOnDrop 0\n                -copyConnectionsOnPaste 0\n                -connectionStyle \"bezier\" \n                -defaultPinnedState 0\n                -additiveGraphingMode 0\n                -connectedGraphingMode 1\n                -settingsChangedCallback \"nodeEdSyncControls\" \n                -traversalDepthLimit -1\n                -keyPressCommand \"nodeEdKeyPressCommand\" \n                -nodeTitleMode \"name\" \n                -gridSnap 0\n                -gridVisibility 1\n                -crosshairOnEdgeDragging 0\n                -popupMenuScript \"nodeEdBuildPanelMenus\" \n                -showNamespace 1\n                -showShapes 1\n                -showSGShapes 0\n                -showTransforms 1\n                -useAssets 1\n                -syncedSelection 1\n                -extendToShapes 1\n                -showUnitConversions 0\n                -editorMode \"default\" \n                -hasWatchpoint 0\n                $editorName;\n\t\t\tif (!$useSceneConfig) {\n"
		+ "\t\t\t\tpanel -e -l $label $panelName;\n\t\t\t}\n\t\t}\n\t}\n\n\n\t$panelName = `sceneUIReplacement -getNextScriptedPanel \"createNodePanel\" (localizedPanelLabel(\"Create Node\")) `;\n\tif (\"\" != $panelName) {\n\t\t$label = `panel -q -label $panelName`;\n\t\tscriptedPanel -edit -l (localizedPanelLabel(\"Create Node\")) -mbv $menusOkayInPanels  $panelName;\n\t\tif (!$useSceneConfig) {\n\t\t\tpanel -e -l $label $panelName;\n\t\t}\n\t}\n\n\n\t$panelName = `sceneUIReplacement -getNextScriptedPanel \"polyTexturePlacementPanel\" (localizedPanelLabel(\"UV Editor\")) `;\n\tif (\"\" != $panelName) {\n\t\t$label = `panel -q -label $panelName`;\n\t\tscriptedPanel -edit -l (localizedPanelLabel(\"UV Editor\")) -mbv $menusOkayInPanels  $panelName;\n\t\tif (!$useSceneConfig) {\n\t\t\tpanel -e -l $label $panelName;\n\t\t}\n\t}\n\n\n\t$panelName = `sceneUIReplacement -getNextScriptedPanel \"renderWindowPanel\" (localizedPanelLabel(\"Render View\")) `;\n\tif (\"\" != $panelName) {\n\t\t$label = `panel -q -label $panelName`;\n\t\tscriptedPanel -edit -l (localizedPanelLabel(\"Render View\")) -mbv $menusOkayInPanels  $panelName;\n"
		+ "\t\tif (!$useSceneConfig) {\n\t\t\tpanel -e -l $label $panelName;\n\t\t}\n\t}\n\n\n\t$panelName = `sceneUIReplacement -getNextPanel \"shapePanel\" (localizedPanelLabel(\"Shape Editor\")) `;\n\tif (\"\" != $panelName) {\n\t\t$label = `panel -q -label $panelName`;\n\t\tshapePanel -edit -l (localizedPanelLabel(\"Shape Editor\")) -mbv $menusOkayInPanels  $panelName;\n\t\tif (!$useSceneConfig) {\n\t\t\tpanel -e -l $label $panelName;\n\t\t}\n\t}\n\n\n\t$panelName = `sceneUIReplacement -getNextPanel \"posePanel\" (localizedPanelLabel(\"Pose Editor\")) `;\n\tif (\"\" != $panelName) {\n\t\t$label = `panel -q -label $panelName`;\n\t\tposePanel -edit -l (localizedPanelLabel(\"Pose Editor\")) -mbv $menusOkayInPanels  $panelName;\n\t\tif (!$useSceneConfig) {\n\t\t\tpanel -e -l $label $panelName;\n\t\t}\n\t}\n\n\n\t$panelName = `sceneUIReplacement -getNextScriptedPanel \"dynRelEdPanel\" (localizedPanelLabel(\"Dynamic Relationships\")) `;\n\tif (\"\" != $panelName) {\n\t\t$label = `panel -q -label $panelName`;\n\t\tscriptedPanel -edit -l (localizedPanelLabel(\"Dynamic Relationships\")) -mbv $menusOkayInPanels  $panelName;\n"
		+ "\t\tif (!$useSceneConfig) {\n\t\t\tpanel -e -l $label $panelName;\n\t\t}\n\t}\n\n\n\t$panelName = `sceneUIReplacement -getNextScriptedPanel \"relationshipPanel\" (localizedPanelLabel(\"Relationship Editor\")) `;\n\tif (\"\" != $panelName) {\n\t\t$label = `panel -q -label $panelName`;\n\t\tscriptedPanel -edit -l (localizedPanelLabel(\"Relationship Editor\")) -mbv $menusOkayInPanels  $panelName;\n\t\tif (!$useSceneConfig) {\n\t\t\tpanel -e -l $label $panelName;\n\t\t}\n\t}\n\n\n\t$panelName = `sceneUIReplacement -getNextScriptedPanel \"referenceEditorPanel\" (localizedPanelLabel(\"Reference Editor\")) `;\n\tif (\"\" != $panelName) {\n\t\t$label = `panel -q -label $panelName`;\n\t\tscriptedPanel -edit -l (localizedPanelLabel(\"Reference Editor\")) -mbv $menusOkayInPanels  $panelName;\n\t\tif (!$useSceneConfig) {\n\t\t\tpanel -e -l $label $panelName;\n\t\t}\n\t}\n\n\n\t$panelName = `sceneUIReplacement -getNextScriptedPanel \"dynPaintScriptedPanelType\" (localizedPanelLabel(\"Paint Effects\")) `;\n\tif (\"\" != $panelName) {\n\t\t$label = `panel -q -label $panelName`;\n\t\tscriptedPanel -edit -l (localizedPanelLabel(\"Paint Effects\")) -mbv $menusOkayInPanels  $panelName;\n"
		+ "\t\tif (!$useSceneConfig) {\n\t\t\tpanel -e -l $label $panelName;\n\t\t}\n\t}\n\n\n\t$panelName = `sceneUIReplacement -getNextScriptedPanel \"scriptEditorPanel\" (localizedPanelLabel(\"Script Editor\")) `;\n\tif (\"\" != $panelName) {\n\t\t$label = `panel -q -label $panelName`;\n\t\tscriptedPanel -edit -l (localizedPanelLabel(\"Script Editor\")) -mbv $menusOkayInPanels  $panelName;\n\t\tif (!$useSceneConfig) {\n\t\t\tpanel -e -l $label $panelName;\n\t\t}\n\t}\n\n\n\t$panelName = `sceneUIReplacement -getNextScriptedPanel \"profilerPanel\" (localizedPanelLabel(\"Profiler Tool\")) `;\n\tif (\"\" != $panelName) {\n\t\t$label = `panel -q -label $panelName`;\n\t\tscriptedPanel -edit -l (localizedPanelLabel(\"Profiler Tool\")) -mbv $menusOkayInPanels  $panelName;\n\t\tif (!$useSceneConfig) {\n\t\t\tpanel -e -l $label $panelName;\n\t\t}\n\t}\n\n\n\t$panelName = `sceneUIReplacement -getNextScriptedPanel \"contentBrowserPanel\" (localizedPanelLabel(\"Content Browser\")) `;\n\tif (\"\" != $panelName) {\n\t\t$label = `panel -q -label $panelName`;\n\t\tscriptedPanel -edit -l (localizedPanelLabel(\"Content Browser\")) -mbv $menusOkayInPanels  $panelName;\n"
		+ "\t\tif (!$useSceneConfig) {\n\t\t\tpanel -e -l $label $panelName;\n\t\t}\n\t}\n\n\n\t$panelName = `sceneUIReplacement -getNextScriptedPanel \"Stereo\" (localizedPanelLabel(\"Stereo\")) `;\n\tif (\"\" != $panelName) {\n\t\t$label = `panel -q -label $panelName`;\n\t\tscriptedPanel -edit -l (localizedPanelLabel(\"Stereo\")) -mbv $menusOkayInPanels  $panelName;\n{ string $editorName = ($panelName+\"Editor\");\n            stereoCameraView -e \n                -camera \"|persp\" \n                -useInteractiveMode 0\n                -displayLights \"default\" \n                -displayAppearance \"wireframe\" \n                -activeOnly 0\n                -ignorePanZoom 0\n                -wireframeOnShaded 0\n                -headsUpDisplay 1\n                -holdOuts 1\n                -selectionHiliteDisplay 1\n                -useDefaultMaterial 0\n                -bufferMode \"double\" \n                -twoSidedLighting 1\n                -backfaceCulling 0\n                -xray 0\n                -jointXray 0\n                -activeComponentsXray 0\n                -displayTextures 0\n"
		+ "                -smoothWireframe 0\n                -lineWidth 1\n                -textureAnisotropic 0\n                -textureHilight 1\n                -textureSampling 2\n                -textureDisplay \"modulate\" \n                -textureMaxSize 32768\n                -fogging 0\n                -fogSource \"fragment\" \n                -fogMode \"linear\" \n                -fogStart 0\n                -fogEnd 100\n                -fogDensity 0.1\n                -fogColor 0.5 0.5 0.5 1 \n                -depthOfFieldPreview 1\n                -maxConstantTransparency 1\n                -objectFilterShowInHUD 1\n                -isFiltered 0\n                -colorResolution 4 4 \n                -bumpResolution 4 4 \n                -textureCompression 0\n                -transparencyAlgorithm \"frontAndBackCull\" \n                -transpInShadows 0\n                -cullingOverride \"none\" \n                -lowQualityLighting 0\n                -maximumNumHardwareLights 0\n                -occlusionCulling 0\n                -shadingModel 0\n"
		+ "                -useBaseRenderer 0\n                -useReducedRenderer 0\n                -smallObjectCulling 0\n                -smallObjectThreshold -1 \n                -interactiveDisableShadows 0\n                -interactiveBackFaceCull 0\n                -sortTransparent 1\n                -controllers 1\n                -nurbsCurves 1\n                -nurbsSurfaces 1\n                -polymeshes 1\n                -subdivSurfaces 1\n                -planes 1\n                -lights 1\n                -cameras 1\n                -controlVertices 1\n                -hulls 1\n                -grid 1\n                -imagePlane 1\n                -joints 1\n                -ikHandles 1\n                -deformers 1\n                -dynamics 1\n                -particleInstancers 1\n                -fluids 1\n                -hairSystems 1\n                -follicles 1\n                -nCloths 1\n                -nParticles 1\n                -nRigids 1\n                -dynamicConstraints 1\n                -locators 1\n                -manipulators 1\n"
		+ "                -pluginShapes 1\n                -dimensions 1\n                -handles 1\n                -pivots 1\n                -textures 1\n                -strokes 1\n                -motionTrails 1\n                -clipGhosts 1\n                -greasePencils 0\n                -shadows 0\n                -captureSequenceNumber -1\n                -width 0\n                -height 0\n                -sceneRenderFilter 0\n                -displayMode \"centerEye\" \n                -viewColor 0 0 0 1 \n                -useCustomBackground 1\n                $editorName;\n            stereoCameraView -e -viewSelected 0 $editorName;\n            stereoCameraView -e \n                -pluginObjects \"gpuCacheDisplayFilter\" 1 \n                $editorName; };\n\t\tif (!$useSceneConfig) {\n\t\t\tpanel -e -l $label $panelName;\n\t\t}\n\t}\n\n\n\tif ($useSceneConfig) {\n        string $configName = `getPanel -cwl (localizedPanelLabel(\"Current Layout\"))`;\n        if (\"\" != $configName) {\n\t\t\tpanelConfiguration -edit -label (localizedPanelLabel(\"Current Layout\")) \n"
		+ "\t\t\t\t-userCreated false\n\t\t\t\t-defaultImage \"vacantCell.xP:/\"\n\t\t\t\t-image \"\"\n\t\t\t\t-sc false\n\t\t\t\t-configString \"global string $gMainPane; paneLayout -e -cn \\\"single\\\" -ps 1 100 100 $gMainPane;\"\n\t\t\t\t-removeAllPanels\n\t\t\t\t-ap false\n\t\t\t\t\t(localizedPanelLabel(\"Persp View\")) \n\t\t\t\t\t\"modelPanel\"\n"
		+ "\t\t\t\t\t\"$panelName = `modelPanel -unParent -l (localizedPanelLabel(\\\"Persp View\\\")) -mbv $menusOkayInPanels `;\\n$editorName = $panelName;\\nmodelEditor -e \\n    -cam `findStartUpCamera persp` \\n    -useInteractiveMode 0\\n    -displayLights \\\"default\\\" \\n    -displayAppearance \\\"smoothShaded\\\" \\n    -activeOnly 0\\n    -ignorePanZoom 0\\n    -wireframeOnShaded 0\\n    -headsUpDisplay 1\\n    -holdOuts 1\\n    -selectionHiliteDisplay 1\\n    -useDefaultMaterial 0\\n    -bufferMode \\\"double\\\" \\n    -twoSidedLighting 0\\n    -backfaceCulling 0\\n    -xray 0\\n    -jointXray 0\\n    -activeComponentsXray 0\\n    -displayTextures 0\\n    -smoothWireframe 0\\n    -lineWidth 1\\n    -textureAnisotropic 0\\n    -textureHilight 1\\n    -textureSampling 2\\n    -textureDisplay \\\"modulate\\\" \\n    -textureMaxSize 32768\\n    -fogging 0\\n    -fogSource \\\"fragment\\\" \\n    -fogMode \\\"linear\\\" \\n    -fogStart 0\\n    -fogEnd 100\\n    -fogDensity 0.1\\n    -fogColor 0.5 0.5 0.5 1 \\n    -depthOfFieldPreview 1\\n    -maxConstantTransparency 1\\n    -rendererName \\\"vp2Renderer\\\" \\n    -objectFilterShowInHUD 1\\n    -isFiltered 0\\n    -colorResolution 256 256 \\n    -bumpResolution 512 512 \\n    -textureCompression 0\\n    -transparencyAlgorithm \\\"frontAndBackCull\\\" \\n    -transpInShadows 0\\n    -cullingOverride \\\"none\\\" \\n    -lowQualityLighting 0\\n    -maximumNumHardwareLights 1\\n    -occlusionCulling 0\\n    -shadingModel 0\\n    -useBaseRenderer 0\\n    -useReducedRenderer 0\\n    -smallObjectCulling 0\\n    -smallObjectThreshold -1 \\n    -interactiveDisableShadows 0\\n    -interactiveBackFaceCull 0\\n    -sortTransparent 1\\n    -controllers 1\\n    -nurbsCurves 1\\n    -nurbsSurfaces 1\\n    -polymeshes 1\\n    -subdivSurfaces 1\\n    -planes 1\\n    -lights 1\\n    -cameras 1\\n    -controlVertices 1\\n    -hulls 1\\n    -grid 1\\n    -imagePlane 1\\n    -joints 1\\n    -ikHandles 1\\n    -deformers 1\\n    -dynamics 1\\n    -particleInstancers 1\\n    -fluids 1\\n    -hairSystems 1\\n    -follicles 1\\n    -nCloths 1\\n    -nParticles 1\\n    -nRigids 1\\n    -dynamicConstraints 1\\n    -locators 1\\n    -manipulators 1\\n    -pluginShapes 1\\n    -dimensions 1\\n    -handles 1\\n    -pivots 1\\n    -textures 1\\n    -strokes 1\\n    -motionTrails 1\\n    -clipGhosts 1\\n    -greasePencils 0\\n    -shadows 0\\n    -captureSequenceNumber -1\\n    -width 1286\\n    -height 740\\n    -sceneRenderFilter 0\\n    $editorName;\\nmodelEditor -e -viewSelected 0 $editorName;\\nmodelEditor -e \\n    -pluginObjects \\\"gpuCacheDisplayFilter\\\" 1 \\n    $editorName\"\n"
		+ "\t\t\t\t\t\"modelPanel -edit -l (localizedPanelLabel(\\\"Persp View\\\")) -mbv $menusOkayInPanels  $panelName;\\n$editorName = $panelName;\\nmodelEditor -e \\n    -cam `findStartUpCamera persp` \\n    -useInteractiveMode 0\\n    -displayLights \\\"default\\\" \\n    -displayAppearance \\\"smoothShaded\\\" \\n    -activeOnly 0\\n    -ignorePanZoom 0\\n    -wireframeOnShaded 0\\n    -headsUpDisplay 1\\n    -holdOuts 1\\n    -selectionHiliteDisplay 1\\n    -useDefaultMaterial 0\\n    -bufferMode \\\"double\\\" \\n    -twoSidedLighting 0\\n    -backfaceCulling 0\\n    -xray 0\\n    -jointXray 0\\n    -activeComponentsXray 0\\n    -displayTextures 0\\n    -smoothWireframe 0\\n    -lineWidth 1\\n    -textureAnisotropic 0\\n    -textureHilight 1\\n    -textureSampling 2\\n    -textureDisplay \\\"modulate\\\" \\n    -textureMaxSize 32768\\n    -fogging 0\\n    -fogSource \\\"fragment\\\" \\n    -fogMode \\\"linear\\\" \\n    -fogStart 0\\n    -fogEnd 100\\n    -fogDensity 0.1\\n    -fogColor 0.5 0.5 0.5 1 \\n    -depthOfFieldPreview 1\\n    -maxConstantTransparency 1\\n    -rendererName \\\"vp2Renderer\\\" \\n    -objectFilterShowInHUD 1\\n    -isFiltered 0\\n    -colorResolution 256 256 \\n    -bumpResolution 512 512 \\n    -textureCompression 0\\n    -transparencyAlgorithm \\\"frontAndBackCull\\\" \\n    -transpInShadows 0\\n    -cullingOverride \\\"none\\\" \\n    -lowQualityLighting 0\\n    -maximumNumHardwareLights 1\\n    -occlusionCulling 0\\n    -shadingModel 0\\n    -useBaseRenderer 0\\n    -useReducedRenderer 0\\n    -smallObjectCulling 0\\n    -smallObjectThreshold -1 \\n    -interactiveDisableShadows 0\\n    -interactiveBackFaceCull 0\\n    -sortTransparent 1\\n    -controllers 1\\n    -nurbsCurves 1\\n    -nurbsSurfaces 1\\n    -polymeshes 1\\n    -subdivSurfaces 1\\n    -planes 1\\n    -lights 1\\n    -cameras 1\\n    -controlVertices 1\\n    -hulls 1\\n    -grid 1\\n    -imagePlane 1\\n    -joints 1\\n    -ikHandles 1\\n    -deformers 1\\n    -dynamics 1\\n    -particleInstancers 1\\n    -fluids 1\\n    -hairSystems 1\\n    -follicles 1\\n    -nCloths 1\\n    -nParticles 1\\n    -nRigids 1\\n    -dynamicConstraints 1\\n    -locators 1\\n    -manipulators 1\\n    -pluginShapes 1\\n    -dimensions 1\\n    -handles 1\\n    -pivots 1\\n    -textures 1\\n    -strokes 1\\n    -motionTrails 1\\n    -clipGhosts 1\\n    -greasePencils 0\\n    -shadows 0\\n    -captureSequenceNumber -1\\n    -width 1286\\n    -height 740\\n    -sceneRenderFilter 0\\n    $editorName;\\nmodelEditor -e -viewSelected 0 $editorName;\\nmodelEditor -e \\n    -pluginObjects \\\"gpuCacheDisplayFilter\\\" 1 \\n    $editorName\"\n"
		+ "\t\t\t\t$configName;\n\n            setNamedPanelLayout (localizedPanelLabel(\"Current Layout\"));\n        }\n\n        panelHistory -e -clear mainPanelHistory;\n        sceneUIReplacement -clear;\n\t}\n\n\ngrid -spacing 5 -size 12 -divisions 5 -displayAxes yes -displayGridLines yes -displayDivisionLines yes -displayPerspectiveLabels no -displayOrthographicLabels no -displayAxesBold yes -perspectiveLabelPosition axis -orthographicLabelPosition edge;\nviewManip -drawCompass 0 -compassAngle 0 -frontParameters \"\" -homeParameters \"\" -selectionLockParameters \"\";\n}\n");
	setAttr ".st" 3;
createNode script -n "sceneConfigurationScriptNode";
	rename -uid "A2585319-4D44-9699-29CE-4894D87BFDC0";
	setAttr ".b" -type "string" "playbackOptions -min 0 -max 60 -ast 0 -aet 180 ";
	setAttr ".st" 6;
createNode polyGear -n "polyGear1";
	rename -uid "9C5D707E-41CE-337A-AFC6-D2A99634E891";
	setAttr ".sides" 15;
	setAttr ".heightDivisions" 3;
createNode polyGear -n "polyGear2";
	rename -uid "CA626BF8-4105-AA5B-0AB1-3DA5C2247F98";
	setAttr ".sides" 15;
	setAttr ".heightDivisions" 3;
createNode polyGear -n "polyGear3";
	rename -uid "BCD11002-4740-2BC9-292E-1A9D0E4CEEFF";
	setAttr ".sides" 15;
	setAttr ".heightDivisions" 3;
createNode polyGear -n "polyGear4";
	rename -uid "47B336EB-43D6-7EE4-F05E-738BED117372";
	setAttr ".sides" 15;
	setAttr ".heightDivisions" 3;
createNode animCurveTL -n "pGear1_translateX";
	rename -uid "75C88D0B-4C84-080A-3B26-6FB036ED7AE4";
	setAttr ".tan" 18;
	setAttr ".wgt" no;
	setAttr -s 28 ".ktv[0:27]"  0 -0.47612383961677551 18 -0.47593009471893311
		 20 -0.40134268999099731 21 -0.32914251089096069 22 -0.27160823345184326 23 -0.16231316328048706
		 24 -0.088037967681884766 25 0.027068812400102615 26 0.10497847944498062 27 0.22723099589347839
		 28 0.31143108010292053 29 0.43924638628959656 30 0.52554988861083984 31 0.65494722127914429
		 32 0.74142491817474365 33 0.87091642618179321 34 0.96066945791244507 35 1.0959129333496094
		 36 1.1859188079833984 37 1.3208613395690918 38 1.4107962846755981 39 1.5456924438476562
		 40 1.6356232166290283 41 1.7705193758010864 43 1.9348503351211548 52 2.3584604263305664
		 56 2.5096774101257324 59 2.6036076545715332;
createNode animCurveTL -n "pGear1_translateY";
	rename -uid "76D27BC8-4977-58EB-BB06-ED846A9820E3";
	setAttr ".tan" 18;
	setAttr ".wgt" no;
	setAttr -s 24 ".ktv[0:23]"  0 6.3642163276672363 6 6.0783829689025879
		 10 5.5475497245788574 14 4.7444939613342285 17 3.9436962604522705 18 3.7563724517822266
		 19 3.5017960071563721 20 3.3754005432128906 21 3.189988374710083 24 3.0124776363372803
		 28 2.6565027236938477 32 2.4757781028747559 35 2.220128059387207 36 2.135587215423584
		 37 1.9884766340255737 38 1.8768472671508789 39 1.6889997720718384 40 1.5501569509506226
		 41 1.3214761018753052 42 1.2166261672973633 45 1.2743148803710938 49 1.3153058290481567
		 55 1.320155143737793 59 1.3022395372390747;
createNode animCurveTL -n "pGear1_translateZ";
	rename -uid "5D983B63-4C35-7F72-64E4-D18ABFDF5E45";
	setAttr ".tan" 18;
	setAttr ".wgt" no;
	setAttr -s 16 ".ktv[0:15]"  0 0.38380187749862671 16 0.38380187749862671
		 18 0.41381850838661194 19 0.45399600267410278 20 0.49850761890411377 21 0.56031423807144165
		 22 0.58032757043838501 28 0.60904163122177124 30 0.60373997688293457 33 0.61204671859741211
		 37 0.64831560850143433 40 0.67495089769363403 49 0.81370341777801514 54 0.88017195463180542
		 58 0.96594971418380737 59 0.99434381723403931;
createNode animCurveTA -n "pGear1_rotateX";
	rename -uid "7D4E0013-4B76-E056-E955-4BA6D3FF8364";
	setAttr ".tan" 18;
	setAttr ".wgt" no;
	setAttr -s 28 ".ktv[0:27]"  0 37.121968855992584 16 37.121963967417926
		 18 42.723834294550642 19 45.595828181342995 21 42.097227043905157 22 39.700265728968283
		 23 35.374570966125212 24 32.402790047427942 25 27.509056040076494 26 24.091563454391402
		 27 17.974883854660945 28 13.304274505258343 29 10.383574497218421 31 10.079738727708504
		 33 10.334002206828599 34 11.025071525386736 35 12.139597947237398 39 14.124488819357104
		 42 13.983893236107338 43 13.369975531808489 44 13.196800281169892 47 13.565780238970056
		 54 13.820693485756522 55 13.111308270975794 56 12.268460986912727 57 10.752122664529951
		 58 9.5634322796371958 59 7.8057616338202038;
createNode animCurveTA -n "pGear1_rotateY";
	rename -uid "71DBAD89-4078-694E-794B-EFAC166474B7";
	setAttr ".tan" 18;
	setAttr ".wgt" no;
	setAttr -s 30 ".ktv[0:29]"  0 1.5902760137009346e-15 16 -1.6809371803229212e-06
		 17 1.1061801154593953 18 2.4399039558067197 19 3.1855440453327346 20 2.1774934234031371
		 21 0.72442164147406651 22 -0.63334308560389085 23 -2.6640104744171729 24 -3.9163981557442078
		 25 -5.6367781798617012 26 -6.7264298632121804 28 -8.8126963493984416 30 -7.3487729437152058
		 31 -5.6766689399159143 32 -4.4457992569796811 33 -2.4264726030534023 34 -0.89039182455917276
		 35 1.6611961939150817 36 3.4647124723346305 37 6.2456591209179555 38 8.1370696948073924
		 39 11.005920830739639 40 12.927334254166841 41 15.802187664986493 42 16.628138337970743
		 45 20.274523432553824 54 26.393624918355059 58 28.903120322486959 59 29.74553325444537;
createNode animCurveTA -n "pGear1_rotateZ";
	rename -uid "EF6DD7DA-445B-F519-B8E8-65B120595427";
	setAttr ".tan" 18;
	setAttr ".wgt" no;
	setAttr -s 27 ".ktv[0:26]"  0 -52.610512214169113 16 -52.610512950422859
		 18 -49.460192858714251 20 -40.574200731605259 21 -34.392314120948519 22 -32.541370359291079
		 24 -29.187916230670421 25 -27.289940706563307 28 -24.464221722144764 29 -28.723740862016282
		 30 -32.198448937859126 31 -37.581465178485999 32 -41.258403296256979 33 -46.895313130461425
		 34 -50.613275017728853 35 -56.193534549905486 36 -59.911231977762895 37 -65.473882791139971
		 38 -69.183108975764753 39 -74.765815818596607 40 -78.512415174250094 41 -84.191961623498742
		 42 -85.431137169471057 45 -93.400041020756717 54 -110.06594973528742 58 -116.7358135298586
		 59 -119.05179777144528;
createNode animCurveTL -n "pGear2_translateX";
	rename -uid "3448BDB1-402D-C878-E435-F69C2E81CFF7";
	setAttr ".tan" 18;
	setAttr ".wgt" no;
	setAttr -s 31 ".ktv[0:30]"  0 0.11338291317224503 15 0.11338291317224503
		 16 0.1119217723608017 17 0.13500788807868958 18 0.16252195835113525 19 0.20635628700256348
		 20 0.23576007783412933 21 0.27981448173522949 22 0.3089139461517334 23 0.35220834612846375
		 24 0.38549548387527466 25 0.43518432974815369 26 0.46829685568809509 27 0.51796120405197144
		 28 0.55380827188491821 29 0.60756808519363403 30 0.64271754026412964 31 0.69981974363327026
		 32 0.73822164535522461 38 1.0385892391204834 39 1.0995042324066162 44 1.3178515434265137
		 47 1.4221318960189819 50 1.3665322065353394 51 1.2962992191314697 52 1.2447326183319092
		 53 1.1702893972396851 56 0.98952430486679077 57 0.91565775871276855 58 0.86731892824172974
		 59 0.79553025960922241;
createNode animCurveTL -n "pGear2_translateY";
	rename -uid "4EE267C0-4FA1-2DBF-BD02-0EA9CBFB6A3B";
	setAttr ".tan" 18;
	setAttr ".wgt" no;
	setAttr -s 24 ".ktv[0:23]"  0 4.848259449005127 6 4.5624260902404785
		 10 4.031592845916748 14 3.2285370826721191 15 2.9345369338989258 16 2.8142826557159424
		 24 2.5390558242797852 30 1.9888668060302734 31 1.8391729593276978 32 1.7269012928009033
		 33 1.5386741161346436 35 1.3120125532150269 36 1.3045060634613037 38 1.2670226097106934
		 42 1.1334090232849121 47 0.84754729270935059 49 0.81661653518676758 50 0.84244024753570557
		 51 0.9078441858291626 52 0.95129048824310303 53 1.0204012393951416 57 1.1865401268005371
		 58 1.2087647914886475 59 1.2353111505508423;
createNode animCurveTL -n "pGear2_translateZ";
	rename -uid "19B00A6E-4964-7BF3-BF3C-4B809ABAFC08";
	setAttr ".tan" 18;
	setAttr ".wgt" no;
	setAttr -s 10 ".ktv[0:9]"  0 -1.6288844347000122 16 -1.6423827409744263
		 17 -1.6895103454589844 21 -1.8607425689697266 30 -2.2187981605529785 36 -2.5842180252075195
		 42 -3.0658218860626221 46 -3.4271879196166992 49 -3.7493717670440674 59 -4.2354874610900879;
createNode animCurveTA -n "pGear2_rotateX";
	rename -uid "243113A8-4D87-EE6F-9427-6B9FF960F5CD";
	setAttr ".tan" 18;
	setAttr ".wgt" no;
	setAttr -s 30 ".ktv[0:29]"  0 -25.431058487667336 15 -25.431054635820193
		 16 -26.348975202152364 17 -28.60088400121791 18 -29.961861879937352 19 -32.454758839724512
		 20 -34.233810996759168 21 -37.653485654443784 22 -40.334931515788213 23 -44.47257269476642
		 24 -48.23277859632838 25 -53.913707756601021 26 -57.711869057111436 27 -63.425355005080213
		 28 -67.673614849105903 29 -74.206882421585789 30 -78.983879132002542 31 -86.304550226758579
		 32 -91.22078124774626 33 -98.615380714902372 35 -109.30780475335466 38 -120.7670099279842
		 40 -129.60700901035906 44 -150.23476887197634 46 -164.32716649780426 47 -174.71699544506183
		 48 177.83666068723724 49 167.19200545484355 51 155.51947389609728 59 142.4863533889563;
createNode animCurveTA -n "pGear2_rotateY";
	rename -uid "3836355D-4371-3209-A5C7-DEBACEA16FEF";
	setAttr ".tan" 18;
	setAttr ".wgt" no;
	setAttr -s 16 ".ktv[0:15]"  0 -25.721771829310583 21 -26.043408295222815
		 31 -29.804367459349645 34 -29.573940405164663 37 -27.251581225699866 39 -25.996306375212011
		 41 -25.947884835349164 44 -27.634418508250832 46 -30.46053667277026 47 -32.773903588032233
		 49 -34.553094866886354 51 -32.385245401928152 56 -24.68660796096993 57 -22.892582079477943
		 58 -21.823610869234887 59 -20.277094911274041;
createNode animCurveTA -n "pGear2_rotateZ";
	rename -uid "E1F0F748-498B-8058-B99E-F0888C5A60AF";
	setAttr ".tan" 18;
	setAttr ".wgt" no;
	setAttr -s 36 ".ktv[0:35]"  0 2.4165730085429327 15 2.4165725614976385
		 16 1.7788450311880952 17 -0.99817362229990125 18 -3.1336604983754626 19 -6.1746339672571455
		 20 -8.1889557460359832 21 -11.027129980074188 22 -12.82347838761468 23 -15.486363884190116
		 24 -16.438217830711501 25 -17.826697689356273 26 -18.719527520083691 27 -20.001010508447226
		 30 -20.373352484841003 31 -19.698170115597321 32 -19.199226633424722 34 -17.960023576748345
		 35 -18.006518587655549 40 -21.585616131095865 42 -23.32143419455409 43 -24.251013418704765
		 46 -22.499168057157537 47 -18.349662424826352 48 -14.268785084363458 49 -4.8596071871800817
		 50 1.770365973769475 51 10.816942525737643 52 16.145087439116487 53 23.129313060356864
		 54 27.171480166478339 55 32.865563006732046 56 36.052422655879049 57 40.487617276173893
		 58 43.20895852085318 59 46.95836248498594;
createNode animCurveTL -n "pGear3_translateX";
	rename -uid "227A387E-43FB-B9A8-4F67-E88DD6005805";
	setAttr ".tan" 18;
	setAttr ".wgt" no;
	setAttr -s 30 ".ktv[0:29]"  0 -1.4806430339813232 10 -1.4815384149551392
		 14 -1.5022087097167969 18 -1.4925159215927124 20 -1.5248644351959229 22 -1.4872403144836426
		 32 -0.99096852540969849 35 -0.81641018390655518 36 -0.77139842510223389 37 -0.70510566234588623
		 38 -0.66010421514511108 39 -0.5930485725402832 40 -0.5479665994644165 41 -0.48013031482696533
		 42 -0.43508312106132507 43 -0.36641538143157959 44 -0.32019981741905212 45 -0.25268304347991943
		 46 -0.20842374861240387 47 -0.14010831713676453 48 -0.089950725436210632 49 -0.013969268649816513
		 50 0.036797892302274704 51 0.11324986815452576 52 0.16482432186603546 53 0.2447771430015564
		 54 0.29482549428939819 55 0.33337506651878357 58 0.39569604396820068 59 0.41072839498519897;
createNode animCurveTL -n "pGear3_translateY";
	rename -uid "5A1CEA5F-4803-6275-55FE-F1BAEF405A44";
	setAttr ".tan" 18;
	setAttr ".wgt" no;
	setAttr -s 22 ".ktv[0:21]"  0 3.2923684120178223 4 3.1698684692382812
		 6 3.0065350532531738 8 2.7751462459564209 9 2.6036462783813477 12 2.2554104328155518
		 13 2.0948436260223389 14 1.978033185005188 15 1.7925287485122681 16 1.6678450107574463
		 17 1.4890912771224976 18 1.3578497171401978 19 1.2513316869735718 22 1.2175432443618774
		 23 1.2370879650115967 26 1.260936975479126 38 1.2802654504776001 47 1.223680853843689
		 50 1.2419612407684326 54 1.228716254234314 56 1.2711368799209595 59 1.2715187072753906;
createNode animCurveTL -n "pGear3_translateZ";
	rename -uid "9625B618-4632-DAF3-889C-19B84398C399";
	setAttr ".tan" 18;
	setAttr ".wgt" no;
	setAttr -s 22 ".ktv[0:21]"  0 0.57412105798721313 9 0.57412105798721313
		 11 0.55624383687973022 14 0.53535395860671997 15 0.52592027187347412 18 0.54688692092895508
		 19 0.58555895090103149 20 0.60760903358459473 21 0.6045612096786499 22 0.6274796724319458
		 23 0.68293571472167969 24 0.72053796052932739 25 0.77496546506881714 26 0.81083053350448608
		 27 0.86067008972167969 29 0.92920362949371338 35 1.0299158096313477 40 1.0311371088027954
		 44 0.97590059041976929 47 0.88931047916412354 51 0.82699805498123169 59 0.81376111507415771;
createNode animCurveTA -n "pGear3_rotateX";
	rename -uid "F821183F-411B-9DD2-71AA-4988A6939A40";
	setAttr ".tan" 18;
	setAttr ".wgt" no;
	setAttr -s 23 ".ktv[0:22]"  0 0 9 0 10 1.7864446662419264 11 8.1520577219071857
		 12 12.95967823783819 13 20.33077254577049 14 25.234041509782049 15 32.823300147575033
		 16 38.366418786877681 17 47.947232804365925 18 54.485589420179863 19 61.112988310086919
		 20 63.670157594399939 21 68.784466030808858 22 72.632138576608597 23 77.551630536700245
		 26 87.351582694496329 27 91.004592363375494 33 98.859787579451975 36 99.807516026170134
		 42 96.376728378090405 51 83.439352952967866 59 79.001747754019092;
createNode animCurveTA -n "pGear3_rotateY";
	rename -uid "819F26D4-441D-1735-DBD8-31BEC883359E";
	setAttr ".tan" 18;
	setAttr ".wgt" no;
	setAttr -s 49 ".ktv[0:48]"  0 0 9 0 10 -0.43233506937497435 11 -2.5212258807652992
		 12 -4.3443338349790981 13 -7.695502628263565 14 -10.431445534265354 15 -15.450562396876125
		 16 -19.549550209759875 17 -27.32890006106868 18 -32.815768041435597 19 -34.024947382226962
		 20 -30.279189596497744 21 -27.435935865960001 22 -26.19372276568625 26 -22.70180411171058
		 27 -21.266232004947426 28 -20.130244687523088 29 -18.220391654328317 30 -16.938130379243454
		 31 -14.88556714437915 32 -13.475470146529307 33 -11.357863149362746 34 -9.9516019023775737
		 35 -7.8822980687675575 36 -6.6134154387090547 37 -5.0706303385353326 38 -4.1460941511263636
		 39 -2.8729723677871708 40 -2.0755488419319716 41 -1.0391935545739484 42 -0.45731067342599541
		 43 0.23849131223950587 44 0.56542595708876442 45 0.53769116118294447 46 0.42713538936728168
		 47 0.36053940640480453 48 0.39067085742621815 49 0.63393845503517454 50 0.90367935001332478
		 51 1.4112927638878079 52 1.8597287092351646 53 2.6538655012697077 54 3.2129021449422561
		 55 1.9755240777790841 56 0.95909643154458568 57 -0.78314284737166806 58 -2.1398338369970791
		 59 -2.4439441792797014;
createNode animCurveTA -n "pGear3_rotateZ";
	rename -uid "EDAE4C8C-4E50-D002-4511-1F9B42281A0F";
	setAttr ".tan" 18;
	setAttr ".wgt" no;
	setAttr -s 43 ".ktv[0:42]"  0 33.825818600287391 9 33.825817117578751
		 10 34.744308094698411 11 38.277344106173153 12 40.793123738786257 13 44.419933107236666
		 14 46.72700918966175 15 49.941130267993344 18 53.875261001129701 19 50.243061376280572
		 20 46.882320609213146 21 41.563127956895471 22 36.947623251833505 23 31.23062213825818
		 24 27.615778066640317 25 22.388745504435366 26 19.052376386922205 27 14.242840098269765
		 28 11.325463230746955 29 7.1181017793886037 30 4.5248093409598464 31 0.79287223962425613
		 32 -1.6382158956264072 33 -5.2214954182510889 34 -7.5804405485539501 35 -11.157738716448822
		 36 -13.504654801004994 37 -16.958402939103685 38 -19.182793442340046 39 -22.569511537504432
		 40 -24.847828077154848 41 -28.286399500432015 42 -30.632648898035118 43 -34.186192543687866
		 44 -36.627764788007624 45 -40.198722896703146 46 -42.583543292568748 47 -46.00299331546249
		 50 -52.913601038427075 52 -58.011154483282731 53 -61.057114635983069 54 -63.028383100719722
		 59 -65.570468976337068;
createNode animCurveTL -n "pGear4_translateX";
	rename -uid "40D2000A-4D8D-5D3A-1DAF-C092BE20B5E1";
	setAttr ".tan" 18;
	setAttr ".wgt" no;
	setAttr -s 38 ".ktv[0:37]"  0 -0.29673653841018677 6 -0.29673653841018677
		 10 -0.31215882301330566 11 -0.32223436236381531 14 -0.34167799353599548 15 -0.35826981067657471
		 17 -0.37498804926872253 25 -0.34473377466201782 27 -0.33854910731315613 28 -0.33096987009048462
		 30 -0.28784728050231934 31 -0.24928909540176392 32 -0.2210957407951355 33 -0.17682303488254547
		 34 -0.14804285764694214 35 -0.099214434623718262 36 -0.06657041609287262 37 -0.017290294170379639
		 38 0.015970587730407715 39 0.066678412258625031 40 0.10127224028110504 41 0.15186205506324768
		 42 0.18498162925243378 43 0.23381471633911133 44 0.26582857966423035 45 0.3136686384677887
		 46 0.34564027190208435 47 0.39321282505989075 48 0.42501738667488098 49 0.47253105044364929
		 50 0.50439399480819702 51 0.55279213190078735 52 0.58561432361602783 53 0.63629764318466187
		 56 0.74632453918457031 57 0.79181766510009766 58 0.82199841737747192 59 0.86730295419692993;
createNode animCurveTL -n "pGear4_translateY";
	rename -uid "CDC4771C-427A-9947-ED3F-1EB709DA902D";
	setAttr ".tan" 18;
	setAttr ".wgt" no;
	setAttr -s 9 ".ktv[0:8]"  0 1.5971828699111938 4 1.4746828079223633
		 5 1.3848494291305542 7 1.2462388277053833 10 1.2228387594223022 12 1.2020266056060791
		 15 1.2174066305160522 17 1.1969259977340698 59 1.2151955366134644;
createNode animCurveTL -n "pGear4_translateZ";
	rename -uid "2ECBB38C-40C9-6CBD-0DD6-E7AFFEC32656";
	setAttr ".tan" 18;
	setAttr ".wgt" no;
	setAttr -s 9 ".ktv[0:8]"  0 -0.74134671688079834 7 -0.75036877393722534
		 9 -0.80167382955551147 15 -0.92308944463729858 17 -0.89650475978851318 19 -0.91546976566314697
		 23 -0.93014705181121826 29 -0.90862798690795898 59 -0.89601516723632812;
createNode animCurveTA -n "pGear4_rotateX";
	rename -uid "CC63C27D-49B3-6C13-7701-23B73D04DB65";
	setAttr ".tan" 18;
	setAttr ".wgt" no;
	setAttr -s 8 ".ktv[0:7]"  0 -82.748219907946378 6 -82.748226534681123
		 9 -86.38341986176799 14 -91.161421533823344 17 -89.65087168667597 22 -90.810721466357947
		 26 -89.746117772369374 59 -89.144803254650313;
createNode animCurveTA -n "pGear4_rotateY";
	rename -uid "CFC6117F-4D38-66CA-A10B-C1BE7F477637";
	setAttr ".tan" 18;
	setAttr ".wgt" no;
	setAttr -s 46 ".ktv[0:45]"  0 0 6 0 7 0.0084705331333049475 8 0.092228724572529883
		 9 0.20973065871882174 10 0.45870842138120727 11 0.7776472671464304 12 0.83560578018727649
		 13 1.0556913899322673 15 1.1356527226235567 16 -0.020419848104296076 17 -1.4369299599675576
		 18 -1.5287433238154127 19 -1.199984505830588 20 -1.1073657649032496 21 -0.97555113264191684
		 22 -0.90191916465398325 23 -0.84468811623341677 24 -0.88021284145228795 25 -0.94695080504648732
		 26 -0.91522001851049961 27 -0.81888612007226214 28 -0.8504439434419373 29 -0.60958835666576883
		 30 -0.47484519420554794 31 -1.0469863200329546 32 -1.1407750499050318 33 -1.184053400855378
		 35 -0.71889752154139752 37 -0.55888410015965895 38 -0.55887197620648577 39 -0.58450514933404174
		 40 -0.57937337805914413 41 -0.58991715901782726 42 -0.57060203734956083 44 -0.60176433039540445
		 47 -0.60089502045817411 49 -0.57433015976941615 51 -0.54479712357427856 52 -0.53453222123543109
		 53 -0.4448977791186669 54 -0.5612838134139696 55 -0.59770665772016518 56 -0.57735656200877628
		 58 -0.52532428366628325 59 -0.49629247245492447;
createNode animCurveTA -n "pGear4_rotateZ";
	rename -uid "9EB8631A-4CB2-D0E8-1A10-818D725CAC89";
	setAttr ".tan" 18;
	setAttr ".wgt" no;
	setAttr -s 45 ".ktv[0:44]"  0 0 6 0 7 0.19086769287119479 8 0.30249604633220084
		 9 0.40599909877986834 10 0.48211311834498882 11 0.79426058416415279 12 1.0067909881578956
		 13 1.4039855687803997 14 1.7509507402612032 15 2.5892938457727182 16 1.268487911781387
		 17 0.14970286906865868 18 0.0066399374773027245 19 -0.23049744728760407 20 -0.33206402368608895
		 21 -0.61912708084860868 22 -0.79593393751859143 23 -0.99351731670863053 24 -1.2792265408624235
		 25 -1.6335087456322737 26 -1.8075105703411567 27 -2.0304174449115702 28 -2.2877753051501912
		 29 -3.6400644770514439 30 -4.7947977284017824 31 -6.891380306678883 32 -8.2380723400838765
		 33 -10.343127102422986 34 -11.950107062015949 35 -14.205775322844467 36 -15.754843880241811
		 37 -18.091028738889154 38 -19.665299428808012 39 -22.07434601151893 40 -23.720771301584218
		 41 -26.197928640422486 42 -27.749812593093964 43 -30.034205745557394 46 -35.315624020411235
		 47 -37.592706118351529 48 -39.072457433635066 54 -50.485451166587893 58 -57.702800183973515
		 59 -59.845997303713958;
select -ne :time1;
	setAttr ".o" 0;
select -ne :hardwareRenderingGlobals;
	setAttr ".otfna" -type "stringArray" 22 "NURBS Curves" "NURBS Surfaces" "Polygons" "Subdiv Surface" "Particles" "Particle Instance" "Fluids" "Strokes" "Image Planes" "UI" "Lights" "Cameras" "Locators" "Joints" "IK Handles" "Deformers" "Motion Trails" "Components" "Hair Systems" "Follicles" "Misc. UI" "Ornaments"  ;
	setAttr ".otfva" -type "Int32Array" 22 0 1 1 1 1 1
		 1 1 1 0 0 0 0 0 0 0 0 0
		 0 0 0 0 ;
	setAttr ".fprt" yes;
select -ne :renderPartition;
	setAttr -s 2 ".st";
select -ne :renderGlobalsList1;
select -ne :defaultShaderList1;
	setAttr -s 5 ".s";
select -ne :postProcessList1;
	setAttr -s 2 ".p";
select -ne :defaultRenderingList1;
select -ne :lightList1;
	setAttr -s 2 ".l";
select -ne :initialShadingGroup;
	setAttr -s 5 ".dsm";
	setAttr ".ro" yes;
select -ne :initialParticleSE;
	setAttr ".ro" yes;
select -ne :defaultRenderGlobals;
	addAttr -ci true -h true -sn "dss" -ln "defaultSurfaceShader" -dt "string";
	setAttr ".imfkey" -type "string" "exr";
	setAttr ".dss" -type "string" "lambert1";
select -ne :defaultResolution;
	setAttr ".pa" 1;
select -ne :defaultLightSet;
	setAttr -s 2 ".dsm";
select -ne :defaultColorMgtGlobals;
	setAttr ".cfe" yes;
	setAttr ".cfp" -type "string" "<MAYA_RESOURCES>/OCIO-configs/Maya2022-default/config.ocio";
	setAttr ".vtn" -type "string" "ACES 1.0 SDR-video (sRGB)";
	setAttr ".vn" -type "string" "ACES 1.0 SDR-video";
	setAttr ".dn" -type "string" "sRGB";
	setAttr ".wsn" -type "string" "ACEScg";
	setAttr ".otn" -type "string" "ACES 1.0 SDR-video (sRGB)";
	setAttr ".potn" -type "string" "ACES 1.0 SDR-video (sRGB)";
select -ne :hardwareRenderGlobals;
	setAttr ".ctrs" 256;
	setAttr ".btrs" 512;
connectAttr "polyPlane1.out" "pPlaneShape1.i";
connectAttr "pGear1_translateX.o" "pGear1.tx";
connectAttr "pGear1_translateY.o" "pGear1.ty";
connectAttr "pGear1_translateZ.o" "pGear1.tz";
connectAttr "pGear1_rotateX.o" "pGear1.rx";
connectAttr "pGear1_rotateY.o" "pGear1.ry";
connectAttr "pGear1_rotateZ.o" "pGear1.rz";
connectAttr "polyGear1.output" "pGearShape1.i";
connectAttr "pGear2_translateX.o" "pGear2.tx";
connectAttr "pGear2_translateY.o" "pGear2.ty";
connectAttr "pGear2_translateZ.o" "pGear2.tz";
connectAttr "pGear2_rotateX.o" "pGear2.rx";
connectAttr "pGear2_rotateY.o" "pGear2.ry";
connectAttr "pGear2_rotateZ.o" "pGear2.rz";
connectAttr "polyGear2.output" "pGearShape2.i";
connectAttr "pGear3_translateX.o" "pGear3.tx";
connectAttr "pGear3_translateY.o" "pGear3.ty";
connectAttr "pGear3_translateZ.o" "pGear3.tz";
connectAttr "pGear3_rotateX.o" "pGear3.rx";
connectAttr "pGear3_rotateY.o" "pGear3.ry";
connectAttr "pGear3_rotateZ.o" "pGear3.rz";
connectAttr "polyGear3.output" "pGearShape3.i";
connectAttr "pGear4_translateX.o" "pGear4.tx";
connectAttr "pGear4_translateY.o" "pGear4.ty";
connectAttr "pGear4_translateZ.o" "pGear4.tz";
connectAttr "pGear4_rotateX.o" "pGear4.rx";
connectAttr "pGear4_rotateY.o" "pGear4.ry";
connectAttr "pGear4_rotateZ.o" "pGear4.rz";
connectAttr "polyGear4.output" "pGearShape4.i";
relationship "link" ":lightLinker1" ":initialShadingGroup.message" ":defaultLightSet.message";
relationship "link" ":lightLinker1" ":initialParticleSE.message" ":defaultLightSet.message";
relationship "shadowLink" ":lightLinker1" ":initialShadingGroup.message" ":defaultLightSet.message";
relationship "shadowLink" ":lightLinker1" ":initialParticleSE.message" ":defaultLightSet.message";
connectAttr "layerManager.dli[0]" "defaultLayer.id";
connectAttr "renderLayerManager.rlmi[0]" "defaultRenderLayer.rlid";
connectAttr "defaultRenderLayer.msg" ":defaultRenderingList1.r" -na;
connectAttr "pointLightShape1.ltd" ":lightList1.l" -na;
connectAttr "pointLightShape2.ltd" ":lightList1.l" -na;
connectAttr "pPlaneShape1.iog" ":initialShadingGroup.dsm" -na;
connectAttr "pGearShape1.iog" ":initialShadingGroup.dsm" -na;
connectAttr "pGearShape2.iog" ":initialShadingGroup.dsm" -na;
connectAttr "pGearShape3.iog" ":initialShadingGroup.dsm" -na;
connectAttr "pGearShape4.iog" ":initialShadingGroup.dsm" -na;
connectAttr "pointLight1.iog" ":defaultLightSet.dsm" -na;
connectAttr "pointLight2.iog" ":defaultLightSet.dsm" -na;
// End of fallinggears.ma
