ps_3_0
def c0, 0.5, 0, 1, 0.25
dcl_texcoord v0.xy
dcl_texcoord3 v1.xy
dcl_color v2
dcl_color1 v3.y
dcl_texcoord2 v4.xyz
dcl_2d s0
dcl_2d s1
texld r0, v0, s0
texld r1, v1, s1
mul r0.w, r1.w, v3.y
lrp r2.xyz, r0.w, r1, r0
mul oC0.xyz, r2, v2
mov oC0.w, c39.x
mad oC1.xyz, v4, c0.x, c0.x
mov oC1.w, c39.x
mad oC2.xyz, v2.w, c0.yyzw, c0.ywyw
mov oC2.w, c39.x
mov r0.yz, c0
mul oC3, r0.zyyy, c52.x
