import json,re,sys
sys.path.insert(0,'.')
from cs_strings import S,P
from cs_rich import R,S_EXTRA,P_EXTRA
P=dict(P); P.update(P_EXTRA)
S=dict(S); S.update(S_EXTRA)
from cs_109 import S109,P109,R109
S.update(S109); P.update(P109); R=dict(R); R.update(R109)
from cs_110 import S110,P110,R110
S.update(S110); P.update(P110); R.update(R110)
from cs_111 import S111,P111,R111
S.update(S111); P.update(P111); R.update({k:v for k,v in R111.items() if v})
from cs_113 import S113,P113,R113
S.update(S113); P.update(P113); R.update(R113)
from cs_114 import S114,P114,R114
S.update({k:v for k,v in S114.items() if v}); P.update(P114); R.update(R114)
from cs_115 import S115,P115,R115
S.update(S115); P.update(P115); R.update(R115)
from cs_115_ha import S115H,R115H
S.update(S115H); R.update(R115H)
from cs_116 import S116,P116,R116
S.update(S116); P.update(P116); R.update(R116)
from cs_119 import S119,P119,R119
S.update(S119); P.update(P119); R.update(R119)
from cs_120 import S120,P120,R120
S.update(S120); P.update(P120); R.update(R120)
from cs_121 import S121,P121,R121
S.update(S121); P.update(P121); R.update(R121)
from cs_122 import S122,P122,R122
S.update(S122); P.update(P122); R.update(R122)
from cs_123 import S123,P123,R123
S.update(S123); P.update(P123); R.update(R123)
from cs_124 import S124,P124,R124
S.update(S124); P.update(P124); R.update(R124)
from cs_125 import S125,P125,R125
S.update(S125); P.update(P125); R.update(R125)
from cs_126 import S126,P126,R126
S.update(S126); P.update(P126); R.update(R126)
from cs_127 import S127,P127,R127
S.update(S127); P.update(P127); R.update(R127)
from cs_128 import S128,P128,R128
S.update(S128); P.update(P128); R.update(R128)
from cs_129 import S129,P129,R129
S.update(S129); P.update(P129); R.update(R129)
from cs_130 import S130,P130,R130
S.update(S130); P.update(P130); R.update(R130)
from cs_131 import S131,P131,R131
S.update(S131); P.update(P131); R.update(R131)
from cs_132 import S132,P132,R132
S.update(S132); P.update(P132); R.update(R132)
from cs_133 import S133,P133,R133
S.update(S133); P.update(P133); R.update(R133)
from cs_134 import S134,P134,R134
S.update(S134); P.update(P134); R.update(R134)
from cs_135 import S135,P135,R135
S.update(S135); P.update(P135); R.update(R135)
from cs_136 import S136,P136,R136
S.update(S136); P.update(P136); R.update(R136)
from cs_137 import S137,P137,R137
S.update(S137); P.update(P137); R.update(R137)
from cs_138 import S138,P138,R138
S.update(S138); P.update(P138); R.update(R138)
from cs_139 import S139,P139,R139
S.update(S139); P.update(P139); R.update(R139)
from cs_140 import S140,P140,R140
S.update(S140); P.update(P140); R.update(R140)
from cs_141 import S141,P141,R141
S.update(S141); P.update(P141); R.update(R141)
from cs_142 import S142,P142,R142
S.update(S142); P.update(P142); R.update(R142)
from cs_143 import S143,P143,R143
S.update(S143); P.update(P143); R.update(R143)
from cs_144 import S144,P144,R144
S.update(S144); P.update(P144); R.update(R144)
from cs_145 import S145,P145,R145
S.update(S145); P.update(P145); R.update(R145)
from cs_146 import S146,P146,R146
S.update(S146); P.update(P146); R.update(R146)
from cs_147 import S147,P147,R147
S.update(S147); P.update(P147); R.update(R147)
from cs_148 import S148,P148,R148
S.update(S148); P.update(P148); R.update(R148)
from cs_149 import S149,P149,R149
S.update(S149); P.update(P149); R.update(R149)
from cs_150 import S150,P150,R150
S.update(S150); P.update(P150); R.update(R150)
from cs_151 import S151,P151,R151
S.update(S151); P.update(P151); R.update(R151)
from cs_152 import S152,P152,R152
S.update(S152); P.update(P152); R.update(R152)
from cs_153 import S153,P153,R153
S.update(S153); P.update(P153); R.update(R153)
from cs_154 import S154,P154,R154
S.update(S154); P.update(P154); R.update(R154)
from cs_155 import S155,P155,R155
S.update(S155); P.update(P155); R.update(R155)
from cs_156 import S156,P156,R156
S.update(S156); P.update(P156); R.update(R156)
from cs_157 import S157,P157,R157
S.update(S157); P.update(P157); R.update(R157)
from cs_158 import S158,P158,R158
S.update(S158); P.update(P158); R.update(R158)
from cs_159 import S159,P159,R159
S.update(S159); P.update(P159); R.update(R159)
from cs_160 import S160,P160,R160
S.update(S160); P.update(P160); R.update(R160)
from cs_161 import S161,P161,R161
S.update(S161); P.update(P161); R.update(R161)
from cs_162 import S162,P162,R162
S.update(S162); P.update(P162); R.update(R162)
from cs_163 import S163,P163,R163
S.update(S163); P.update(P163); R.update(R163)
from cs_164 import S164,P164,R164
S.update(S164); P.update(P164); R.update(R164)
from cs_165 import S165,P165,R165
S.update(S165); P.update(P165); R.update(R165)
from cs_166 import S166, P166
S.update(S166); P.update(P166)
from cs_167 import S167, P167, R167
S.update(S167); P.update(P167); R.update(R167)
from cs_168 import S168, P168
S.update(S168); P.update(P168)
from cs_169 import S169
S.update(S169)
from cs_170 import S170, P170
S.update(S170); P.update(P170)
from cs_171 import S171
S.update(S171)
from cs_172 import S172
S.update(S172)
from cs_173 import S173
S.update(S173)
from cs_174 import S174, P174
S.update(S174); P.update(P174)
from cs_175 import S175
S.update(S175)
from cs_176 import S176, P176
S.update(S176); P.update(P176)
from cs_177 import S177, P177
S.update(S177); P.update(P177)
from cs_178 import S178, P178
S.update(S178); P.update(P178)
from cs_179 import S179, P179
S.update(S179); P.update(P179)
from cs_180 import S180, P180
S.update(S180); P.update(P180)
from cs_181 import S181, P181
S.update(S181); P.update(P181)
from cs_182 import S182, P182
S.update(S182); P.update(P182)
from cs_183 import S183, P183
S.update(S183); P.update(P183)
from cs_184 import S184, P184
S.update(S184); P.update(P184)
from cs_185 import S185, P185
S.update(S185); P.update(P185)
from cs_186 import S186, P186
S.update(S186); P.update(P186)
from cs_187 import S187, P187
S.update(S187); P.update(P187)
from cs_188 import S188, P188
S.update(S188); P.update(P188)
from cs_189 import S189, P189
S.update(S189); P.update(P189)
from cs_190 import S190, P190, R190
S.update(S190); P.update(P190); R.update(R190)
from cs_191 import S191, P191, R191
S.update(S191); P.update(P191); R.update(R191)
from cs_192 import S192, P192
S.update(S192); P.update(P192)
from cs_193 import S193, P193, R193
S.update(S193); P.update(P193); R.update(R193)
from cs_194 import S194, P194, R194
S.update(S194); P.update(P194); R.update(R194)
from cs_195 import S195, P195
S.update(S195); P.update(P195)
from cs_196 import S196, P196, R196
S.update(S196); P.update(P196); R.update(R196)
from cs_197 import S197, P197
S.update(S197); P.update(P197)
from cs_198 import S198, P198, R198
S.update(S198); P.update(P198); R.update(R198)
from cs_199 import S199, P199, R199
S.update(S199); P.update(P199); R.update(R199)
from cs_200 import S200, P200, R200
S.update(S200); P.update(P200); R.update(R200)
from cs_201 import S201, P201, R201
S.update(S201); P.update(P201); R.update(R201)
from cs_202 import S202, P202, R202
S.update(S202); P.update(P202); R.update(R202)
from cs_203 import S203, P203, R203
S.update(S203); P.update(P203); R.update(R203)
from cs_204 import S204, P204, R204
S.update(S204); P.update(P204); R.update(R204)
from cs_205 import S205, P205, R205
for _k, _v in S205.items(): S.setdefault(_k, _v)
P.update(P205)
for _k, _v in R205.items(): R.setdefault(_k, _v)
from cs_206 import S206, P206, R206
for _k, _v in S206.items(): S.setdefault(_k, _v)
for _k, _v in P206.items(): P.setdefault(_k, _v)
from cs_207 import S207, P207
for _k, _v in S207.items(): S.setdefault(_k, _v)
for _k, _v in P207.items(): P.setdefault(_k, _v)
from cs_208 import S208, P208
for _k, _v in S208.items(): S.setdefault(_k, _v)
for _k, _v in P208.items(): P.setdefault(_k, _v)
from cs_209 import S209, P209
for _k, _v in S209.items(): S.setdefault(_k, _v)
for _k, _v in P209.items(): P.setdefault(_k, _v)
from cs_210 import S210, P210
for _k, _v in S210.items(): S.setdefault(_k, _v)
for _k, _v in P210.items(): P.setdefault(_k, _v)
from cs_211 import S211, P211
for _k, _v in S211.items(): S.setdefault(_k, _v)
for _k, _v in P211.items(): P.setdefault(_k, _v)
from cs_212 import S212, P212
for _k, _v in S212.items(): S.setdefault(_k, _v)
for _k, _v in P212.items(): P.setdefault(_k, _v)
from cs_213 import S213, P213
for _k, _v in S213.items(): S.setdefault(_k, _v)
for _k, _v in P213.items(): P.setdefault(_k, _v)
from cs_214 import S214, P214
for _k, _v in S214.items(): S.setdefault(_k, _v)
for _k, _v in P214.items(): P.setdefault(_k, _v)
from cs_215 import S215, P215
for _k, _v in S215.items(): S.setdefault(_k, _v)
for _k, _v in P215.items(): P.setdefault(_k, _v)
from cs_216 import S216, P216
for _k, _v in S216.items(): S.setdefault(_k, _v)
for _k, _v in P216.items(): P.setdefault(_k, _v)
P.pop('{0} out', None)    # took 'timed out' (1.0.103)
for _k in list(S):
    if '<' in _k and re.search(r'</?(b|i|code|kbd|em|strong)>', _k):
        R.setdefault(_k, S.pop(_k))   # tags only ever match as rich (1.0.103)
for _k in [k for k in P if re.search(r'</?(b|i|code|kbd|em|strong)>', k)]:
    R.setdefault(_k, P.pop(_k))
S.update({'Czech':'čeština','English':'angličtina'})
S.pop("isemon reads a token server from two files under /var/log/remote/<host>/: totp.cgi.log and radius-detail.log. Its rsyslog needs a rule for both program names - deploy/isemon/11-otp.conf in this package is the one; put it on the isemon machine and restart rsyslog.",None)
reuse=json.load(open('isemon_reuse.json'))
for k,v in reuse['ex'].items(): S.setdefault(k,v)
for k,v in reuse['keep'].items():
    if ' ' in k.strip() and not re.search(r'[\-/]{2}|^[a-z]+ [a-z]+$',k): S.setdefault(k,v)
skipP={'toast show{0}','&kind={0}','Let {0} back in','policy {0}','isemon {0}','systemctl restart {0}','Remove {0}'}
for k,v in reuse['pk'].items():
    if k not in skipP: P.setdefault(k,v)
seen=set(open('src_strings.txt').read().split('\n'))
missing=[s for s in seen if s not in S and not s.startswith('otp --set')]
print('untranslated crawled:',len(missing))
for m in missing: print('  ',m)
# 1.0.172: "the web address" became "the VIP address" in every source - each
# translation of a text that said it follows it, the old ones kept as they are.
import vipname
for _d in (S, P, R):
    for _k, _v in list(_d.items()):
        _n = vipname.en(_k)
        if _n != _k and _n not in _d:
            _d[_n] = vipname.cs(_v)
def ids(d,pre):
    out={}
    for i,(k,v) in enumerate(sorted(d.items())):
        out['%s%04d'%(pre,i+1)]={'source':k,'text':v}
    return out
pack={'_meta':{'code':'cs','name':'Čeština','english':'Czech','version':'1.0.195','made':'2026-10-23',
  'about':'Texty stránek otp v češtině. Stejná ID jako en.json; měňte jen "text", nikdy "source". Prázdný text znamená: zobrazit anglicky.'},
  'strings':ids(S,'s'),'patterns':ids(P,'p'),'rich':ids(R,'r')}
out='/home/claude/build/out/otp-1.0.195/web/lang/cs.json'
json.dump(pack,open(out,'w'),ensure_ascii=False,indent=1)
print(len(S),len(P),len(R))
