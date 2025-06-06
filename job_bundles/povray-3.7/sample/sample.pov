#version 3.7;

// Include standard POV-Ray files
#include "colors.inc"
#include "textures.inc"
#include "metals.inc"
#include "glass.inc"

// Global settings
global_settings {
    assumed_gamma 1.0
    ambient_light <0.2, 0.2, 0.3>
    radiosity {
        brightness 0.8
        count 50
    }
}

// Camera setup
camera {
    location <5, 8, -12>
    look_at <0, 2, 0>
    angle 35
}

// Background
background { color <0.05, 0.1, 0.2> }

// Main light source (sun-like)
light_source {
    <10, 20, -10>
    color rgb <1.0, 0.9, 0.7>
    area_light <2, 0, 0>, <0, 2, 0>, 5, 5
    adaptive 2
    jitter
}

// Colored accent lights
light_source {
    <-8, 5, 5>
    color rgb <0.3, 0.7, 1.0>
    fade_distance 15
    fade_power 2
}

light_source {
    <8, 3, 8>
    color rgb <1.0, 0.3, 0.5>
    fade_distance 12
    fade_power 2
}

// Ground plane with interesting texture
plane {
    y, 0
    texture {
        pigment {
            checker
            color rgb <0.1, 0.1, 0.2>
            color rgb <0.2, 0.2, 0.3>
            scale 2
        }
        normal {
            bumps 0.3
            scale 0.5
        }
        finish {
            ambient 0.1
            diffuse 0.7
            reflection 0.2
        }
    }
}

// Central crystal structure
union {
    // Main crystal prism
    prism {
        0, 6, 6
        <0, 2>, <1.5, 1>, <1.5, -1>, <0, -2>, <-1.5, -1>, <-1.5, 1>
        rotate <0, 0, 90>
        translate <0, 3, 0>
    }
    
    // Crystal top
    cone {
        <0, 6, 0>, 1.5
        <0, 8, 0>, 0
    }
    
    texture {
        pigment { color rgbf <0.9, 0.95, 1.0, 0.8> }
        finish {
            ambient 0.1
            diffuse 0.3
            reflection 0.8
            specular 1.0
            roughness 0.001
            ior 1.5
        }
    }
    interior {
        ior 1.5
        caustics 1.0
    }
}

// Floating metallic spheres
sphere {
    <-4, 4, 3>, 1
    texture {
        T_Gold_1A
        finish {
            reflection 0.9
            specular 1.0
            metallic
        }
    }
    rotate <0, clock*60, 0>
}

sphere {
    <4, 3, -2>, 0.8
    texture {
        T_Silver_1A
        finish {
            reflection 0.95
            specular 1.0
            metallic
        }
    }
    rotate <0, -clock*45, 0>
}

sphere {
    <-2, 6, -4>, 0.6
    texture {
        T_Copper_1A
        finish {
            reflection 0.8
            specular 1.0
            metallic
        }
    }
    rotate <0, clock*90, 0>
}

// Geometric torus
torus {
    2, 0.5
    rotate <90, 0, 0>
    translate <3, 1.5, 4>
    texture {
        pigment {
            gradient x
            color_map {
                [0.0 color rgb <1, 0, 0>]
                [0.5 color rgb <0, 1, 0>]
                [1.0 color rgb <0, 0, 1>]
            }
            scale 4
        }
        finish {
            ambient 0.2
            diffuse 0.8
            specular 0.5
        }
    }
}

// Abstract sculpture made of boxes
union {
    box { <-0.5, 0, -0.5>, <0.5, 2, 0.5> }
    box { <-1, 1, -0.3>, <1, 1.5, 0.3> }
    box { <-0.3, 1.5, -1>, <0.3, 2, 1> }
    
    translate <-6, 0, -2>
    rotate <0, 30, 0>
    
    texture {
        pigment {
            marble
            color_map {
                [0.0 color rgb <0.2, 0.1, 0.5>]
                [0.5 color rgb <0.8, 0.4, 0.9>]
                [1.0 color rgb <0.3, 0.2, 0.7>]
            }
            scale 2
        }
        normal {
            granite 0.5
            scale 0.3
        }
        finish {
            ambient 0.15
            diffuse 0.85
            phong 0.5
        }
    }
}

// Spiral helix
#declare R = 2;
#declare Turns = 3;
#declare Height = 6;
#declare Steps = 100;

union {
    #local I = 0;
    #while (I < Steps)
        #local Angle = (I / Steps) * 360 * Turns;
        #local Y = (I / Steps) * Height;
        #local X = R * cos(radians(Angle));
        #local Z = R * sin(radians(Angle));
        
        sphere {
            <X, Y, Z>, 0.1
            texture {
                pigment { color rgb <1, 0.5, 0> }
                finish {
                    ambient 0.3
                    diffuse 0.7
                    specular 0.8
                }
            }
        }
        #local I = I + 1;
    #end
    
    translate <6, 1, -6>
}

// Floating glass pyramid
object {
    intersection {
        plane { y, 0 }
        plane { x + y, 0 rotate <0, 0, -45> }
        plane { -x + y, 0 rotate <0, 0, 45> }
        plane { z + y, 0 rotate <45, 0, 0> }
        plane { -z + y, 0 rotate <-45, 0, 0> }
    }
    scale <2, 3, 2>
    translate <0, 7, -8>
    
    texture {
        pigment { color rgbf <0.8, 1.0, 0.9, 0.9> }
        finish {
            ambient 0.05
            diffuse 0.2
            reflection 0.7
            specular 1.0
            roughness 0.001
            ior 1.33
        }
    }
    interior {
        ior 1.33
        caustics 1.0
    }
}

// Atmospheric fog for depth
fog {
    fog_type 2
    distance 20
    color rgb <0.1, 0.15, 0.2>
    fog_offset 0.1
    fog_alt 1.0
    turbulence 0.8
}