ps_3_0
def c0, 0, -1, -0, 9.99999975e-006
def c1, 3.99600005, 4, 0.125, 0.25
def c2, 0.5, 0, 1, 0.25
dcl_texcoord v0.xy
dcl_texcoord1 v1.xyz
dcl_color v2.xw
dcl vPos.xy
dcl_2d s0
dcl_2d s10
mov_sat r0.x, c39.x
mul r0.x, r0.x, c1.x
frc r0.y, r0.x
mul r0.z, r0.y, c1.y
frc r0.w, r0.z
add r1.xy, r0.zxzw, -r0.wyzw
mul r0.xy, c1.z, vPos
frc r0.xy, r0_abs
cmp r0.xy, vPos, r0, -r0
mul r0.xy, r0, c1.w
mad r0.xy, r1, c1.w, r0
mov r0.zw, c0.x
texldl r0, r0, s10
cmp r0, -r0.y, c0.y, c0.z
texkill r0
texld r0, v0, s0
add r1.xyz, c0.w, v1
dp3 r1.w, r1, r1
rsq r1.w, r1.w
mul r0.w, r0.w, v2.w
mad r1.xyz, r1, r1.w, -c0.y
mul oC1.xyz, r1, c2.x
mul r0.w, r0.w, c39.x
mov oC0, r0
mov oC1.w, r0.w
mad oC2.xyz, v2.x, c2.yyzw, c2.ywyw
mov oC2.w, r0.w
mov r0.yz, c0
mul oC3, -r0.yzzz, c52.x
