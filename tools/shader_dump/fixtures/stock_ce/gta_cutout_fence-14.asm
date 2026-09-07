ps_3_0
def c0, 0.176470593, -1, -0, 9.99999975e-006
def c1, 0.5, 0, 1, 0.25
dcl_texcoord v0.xy
dcl_texcoord1 v1.xyz
dcl_color v2.xw
dcl_2d s0
texld r0, v0, s0
mul r0.w, r0.w, v2.w
mul r1.x, r0.w, c39.x
mov r2.xyz, c0
mad r0.w, r0.w, -c39.x, r2.x
cmp r3, r0.w, c0.y, c0.z
texkill r3
add r1.yzw, c0.w, v1.xxyz
dp3 r0.w, r1.yzww, r1.yzww
rsq r0.w, r0.w
mad r1.yzw, r1, r0.w, -c0.y
mul oC1.xyz, r1.yzww, c1.x
mov oC0.xyz, r0
mov oC0.w, r1.x
mov oC1.w, r1.x
mad oC2.xyz, v2.x, c1.yyzw, c1.ywyw
mov oC2.w, r1.x
mul oC3, -r2.yzzz, c52.x
