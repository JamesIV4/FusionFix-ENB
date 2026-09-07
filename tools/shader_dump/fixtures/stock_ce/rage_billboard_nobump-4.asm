ps_3_0
def c0, 0.200000003, 1, -0.5, 0
dcl_texcoord v0
dcl_2d s0
dcl_2d s1
mul r0.xy, v0.z, v0
frc r0.xy, r0
texld r0, r0, s1
mul r0.x, r0.w, v0.z
mul r0.x, r0.x, c66.w
mad r0.xy, r0.x, c0.x, v0
texld r0, r0, s0
dp4 r0.x, r0, c0.y
add r0.x, r0.x, c0.z
cmp r0, r0.x, -c0.w, -c0.y
texkill r0
mul oC0.y, v0.w, v0.w
mad oC0.xzw, v0.w, c0.yyww, c0.wywy
