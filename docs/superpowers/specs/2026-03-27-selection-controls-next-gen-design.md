# 涓嬩竴浠ｉ€夋嫨鎺т欢浼樺寲鏂规璁捐

- 鏃ユ湡锛?026-03-27
- 鑼冨洿锛欳heckbox / Radio / Toggle / 閫変腑鍒楄〃 / 棰勮鍒囨崲 / 瀵艰埅閫変腑鎬?- 褰撳墠闃舵浼樺厛绾э細鍏堝仛 Checkbox / Radio锛屽叡浜富棰樺寲锛涘悗缁悜閫夋嫨鎺т欢瀹舵棌鎵╁睍

---

> [!IMPORTANT]
> **Status update (2026-03-28):**
> - This spec is now historical context for the **shared QSS** phase.
> - The current runtime boundary has already narrowed to `build_checkbox_stylesheet()` for Checkbox only.
> - Radio / Slider are no longer expected to evolve on top of `QRadioButton::indicator` / `QSlider::handle` QSS.
> - For the active geometry route, use `2026-03-28-project-level-themed-selection-controls-design.md`.

## 1. 鑳屾櫙

褰撳墠椤圭洰鐨勫熀纭€ UI 宸茬粡瀹屾垚涓€杞粺涓€锛?
- 鎸夐挳銆佽緭鍏ユ銆丆ombo銆佸脊灞傛牱寮忓凡缁忔敹鍙ｅ埌鍏变韩涓婚浣撶郴
- PyQt5 宸茶縼绉诲埌 PySide6锛屾簮鐮?MIT 鍙戝竷璺嚎宸茬粡鎴愮珛
- 棰勮绐楀彛涓庣湡瀹炵晫闈㈠凡缁忚兘澶熷叡鐢ㄨ秺鏉ヨ秺澶氱殑 shared UI 鍩哄缓

浣嗏€滈€夋嫨绫绘帶浠垛€濅粛鐒朵笉鏄畬鏁寸殑涓€浠ｄ骇鍝佽瑷€锛?
1. `AppTheme` 閲屽凡鏈?button / input / combo token锛屼絾缂哄皯 checkbox / radio 涓撶敤 token
2. `heading_numbering_styles.py` 閲屼粛鏈夊眬閮?`QCheckBox` 鏍峰紡
3. Checkbox / Radio / Toggle / 鍒楄〃閫変腑鎬?/ 瀵艰埅閫変腑鎬佷箣闂磋繕娌℃湁褰㈡垚缁熶竴鑺傚
4. 褰撳墠棰勮鍙帴鍙楋紝浣嗚繕娌℃湁杈惧埌鈥滀笅涓€浠ｄ紭鍖栨柟妗堚€濈殑瀹屾暣鏍囧噯

鍥犳锛岃繖娆＄殑鐩爣涓嶅啀鏄€滃崟鐙慨 QCheckBox/QRadioButton鈥濓紝鑰屾槸锛?
> 寤虹珛涓€濂?Selection Controls锛堥€夋嫨鎺т欢锛夎瑙夎瑷€锛屽苟鍏堣惤鍦板埌 Checkbox / Radio銆?
鍚屾椂锛岃繖濂楁柟妗堜笉搴旀槸灏侀棴鐨勫唴閮ㄨ嚜鍡ㄣ€?
浣犳柊澧炵殑瑕佹眰鏄細

> 瑕佹寔缁í鍚戝姣斿紑婧愪紭绉€鎺т欢瀹舵棌鐨勬瀯寤烘柟寮忥紝骞舵嵁姝や笉鏂紭鍖栥€?
杩欐剰鍛崇潃鏈鏂规闄や簡鈥滃仛鍑烘潵鈥濓紝杩樿鍏峰锛?
- 瀵规爣澶栭儴浼樼浣撶郴鐨勮緭鍏ユ満鍒?- 灏嗗弬鑰冭浆璇戜负鍐呴儴 token / builder / 鐘舵€佽瑷€鐨勮兘鍔?- 鎸佺画杩唬鑰屼笉鏄竴閿ゅ瓙涔板崠鐨勪紭鍖栬妭濂?
---

## 2. 鏍稿績鐩爣

### 2.1 浜у搧鐩爣

寤虹珛鈥滀笅涓€浠ｉ€夋嫨鎺т欢椋庢牸鈥濓紝璁╀互涓嬪厓绱犻€愭鐪嬭捣鏉ュ儚鍚屼竴浠ｄ骇鍝侊細

- Checkbox
- Radio
- ToggleSwitch
- 鍒楄〃閫変腑鎬?- 棰勮鍒囨崲
- 宸︿晶瀵艰埅閫変腑鎬?- 鍗＄墖閫変腑鎬?
### 2.2 褰撳墠杩唬鐩爣

褰撳墠杩欎竴杞彧鍋氱涓€闃舵锛?
1. 缁?Checkbox / Radio 瀹氫箟瀹屾暣瑙嗚璇█
2. 鍋氭垚鍏变韩涓婚鏍峰紡锛屼笉鍙敼 preview
3. 璁╅瑙堝拰鐪熷疄鐣岄潰璧板悓涓€濂楀疄鐜?4. 涓虹浜岄樁娈垫墿灞曞埌 Toggle / 閫変腑鍒楄〃 / 瀵艰埅鑺傚鎵撳熀纭€

### 2.3 鎸佺画浼樺寲鐩爣

寤虹珛涓€涓暱鏈熸湁鏁堢殑妯悜瀵规爣鏈哄埗锛?
1. 鎸佺画瑙傚療浼樼寮€婧愭帶浠跺鏃忓浣曞畾涔夌粍浠惰竟鐣?2. 瀵规瘮瀹冧滑濡備綍澶勭悊 selection controls 鐨勫嚑浣曘€佺姸鎬併€佸竷灞€涓庡眰绾?3. 涓嶇洿鎺ユ妱瀹炵幇锛岃€屾槸鎶藉彇涓烘湰椤圭洰鑷繁鐨?token / 瑙勫垯 / builder
4. 姣忚疆浼樺寲閮借兘鍥炲埌 preview + 鐪熷疄鐣岄潰涓鏍?
---

## 3. 瑙嗚鏂瑰悜閫夊瀷

鏈鍏辨湁涓夌鍙€夋柟鍚戯細

### 鏂规 A锛氭煍鍜屾贩鍚堢増锛堟帹鑽愶級

鐗圭偣锛?
- 鏈?macOS 鐨勭簿鑷村嚑浣?- 閫変腑鐘舵€佹瘮 macOS 鏇存竻妤?- 鏈?Fluent 鐨勬竻鏅扮姸鎬佹劅锛屼絾涓嶈繃搴︽姠鎴?- 涓庣幇鏈夊亸鍏嬪埗鐨勬寜閽綋绯绘渶鍖归厤

### 鏂规 B锛氬亸 macOS 鐗?
鐗圭偣锛?
- 鏇磋交銆佹洿绉€姘?- 鏇村亸缁嗚吇銆佸厠鍒?
缂虹偣锛?
- 鐘舵€佸姏搴︾暐寮?- 鍦ㄥ鏉傞厤缃潰鏉块噷涓嶄竴瀹氬娓呮

### 鏂规 C锛氬亸 Fluent 鐗?
鐗圭偣锛?
- 鏇寸幇浠ｃ€佹洿閱掔洰
- 鐘舵€佹洿鐩存帴

缂虹偣锛?
- 瀹规槗鎶㈡垙
- 涓庡綋鍓嶆寜閽綋绯汇€佽緭鍏ユ浣撶郴鐨勫厠鍒舵劅涓嶅畬鍏ㄤ竴鑷?
### 鏈€缁堥€夋嫨

鏈閫夋嫨锛?
> **鏌斿拰娣峰悎鐗?2.0**

鍗筹細

- 鍑犱綍璇█鍋?macOS
- 鐘舵€佽瑷€鍚告敹 Fluent 鐨勬竻鏅板害
- 鑺傚鎺у埗淇濇寔褰撳墠椤圭洰鈥滀笓涓氬伐鍏锋劅鈥?
浣嗗湪瀹炵幇鏂规硶涓婏紝涓嶉噰鐢ㄥ崟涓€骞冲彴鐨勭収鎼紝鑰岄噰鐢細

> **椋庢牸娣峰悎 + 缁撴瀯瀵规爣**

涔熷氨鏄細

- 椋庢牸鍙傝€冿細macOS / Fluent / Adwaita
- 鏋勫缓鏂规硶鍙傝€冿細浼樼寮€婧愭帶浠跺鏃?- 鏈€缁堜骇鐗╋細椤圭洰鑷繁鐨勫叡浜富棰樼郴缁?
---

## 3.1 妯悜瀵规爣瀵硅薄锛堢涓€鎵癸級

鏈」鐩悗缁寔缁紭鍖栨椂锛屼紭鍏堝弬鑰冧互涓嬪紑婧愪綋绯荤殑鈥滄瀯寤烘柟寮忊€濓紝鑰屼笉鐩存帴绉绘鍏朵唬鐮侊細

### A. Libadwaita锛圙NOME锛?
鍙傝€冪偣锛?
- style classes 鐨勫眰娆″寲缁勭粐
- `boxed-list` / `card` / `navigation-sidebar` 杩欑被鈥滆涔夊寲鏍峰紡绫烩€?- `selection-mode` check button 鐨勪笓闂ㄨ瑙夎瑷€
- `AdwToolbarView`銆乥reakpoint銆乤daptive layout 杩欑被缁撴瀯鎬ч€傞厤鎬濊矾

鍊煎緱瀛︿範鐨勫湴鏂癸細

1. 瀹冧笉鏄彧鍋氬崟鎺т欢濂界湅锛岃€屾槸鎶婃帶浠舵斁杩涒€滃崱鐗?/ 鍒楄〃 / 瀵艰埅 / 宸ュ叿鏍忊€濇暣浣撹澧冮噷
2. 瀹冩妸璁稿瑙嗚宸紓鎶芥垚鈥滆涔夋牱寮忕被鈥濓紝鑰屼笉鏄瘡椤靛伔鍋峰啓涓€濂?3. 瀹冨己璋冨悓涓€涓帶浠跺湪涓嶅悓瀹瑰櫒璇涓殑鍗忚皟鍏崇郴

### B. Kirigami锛圞DE锛?
鍙傝€冪偣锛?
- 鍏堟槑纭€滆鐢ㄥ摢绉嶆帶浠垛€濓紝鍐嶈皥鏍峰紡
- selection controls銆乥uttons銆乻liders銆乼ext fields 閮界撼鍏ョ粺涓€浜や簰鍒嗙被
- 鑷€傚簲鐣岄潰涓嶆槸闄勫姞鐗规€э紝鑰屾槸缁勪欢浣撶郴鐨勪竴閮ㄥ垎

鍊煎緱瀛︿範鐨勫湴鏂癸細

1. 鍏堝仛鎺т欢鑱岃矗杈圭晫锛屽啀鍋氳瑙?2. 寮鸿皟鈥滄帶浠剁被鍨嬮€夋嫨姝ｇ‘鈥濇湰韬氨鏄骇鍝佽川閲忕殑涓€閮ㄥ垎
3. 缁勪欢瀹舵棌鐨勭粺涓€鏉ヨ嚜浣跨敤瑙勫垯鍜屼氦浜掕涔夛紝涓嶅彧鏄?QSS

### C. QFluentWidgets锛堝弬鑰冪粨鏋勶紝涓嶅紩鍏ヤ唬鐮侊級

鍙傝€冪偣锛?
- gallery 椹卞姩鐨勬帶浠跺鏃忓睍绀烘柟寮?- 浠ョ粍浠跺簱 + 绀轰緥搴撶殑褰㈠紡缁勭粐璁ょ煡
- 鍚屼竴瑙嗚浣撶郴涓嬬粍浠跺懡鍚嶃€佸睍绀恒€佸垎缁勯兘杈冨畬鏁?
鍊煎緱瀛︿範鐨勫湴鏂癸細

1. gallery 涓嶅彧鏄?demo锛岃€屾槸缁勪欢璇█鐨勯獙璇侀潰
2. 缁勪欢瀹舵棌闇€瑕佲€滃彲灞曠ず銆佸彲瀵规瘮銆佸彲宸℃鈥濈殑缁熶竴鍏ュ彛
3. 棰勮澹冲鏋滃拰鐪熷疄缁勪欢鍏辩敤瀹炵幇锛屽氨鑳藉舰鎴愭寔缁紭鍖栭棴鐜?
娉ㄦ剰锛?
- QFluentWidgets 浠撳簱褰撳墠鍏紑璇存槑涓?GPLv3 / 鍟嗕笟璁稿彲璺嚎
- 鍥犳杩欓噷鍙妸瀹冨綋浣?*缁撴瀯涓庡睍绀烘柟娉曞弬鑰?*
- 涓嶆妸鍏朵唬鐮併€佽祫婧愭垨鍙楅檺瀹炵幇鐩存帴绾冲叆褰撳墠 MIT 婧愮爜浠撳簱

---

## 3.2 瀵规爣杈撳嚭鍘熷垯

妯悜瀵规爣涓嶆槸涓轰簡鈥滃儚璋佲€濓紝鑰屾槸涓轰簡鎶藉彇杩欎簺闂鐨勬洿浼樼瓟妗堬細

1. 涓€涓帶浠跺鏃忓浣曞懡鍚嶅拰鍒嗗眰锛?2. 鍝簺鐘舵€佸簲璇ユ槸 token锛屽摢浜涘簲璇ユ槸璇箟绫伙紵
3. preview 濡備綍鎴愪负鐪熷疄缁勪欢鐨勯獙璇侀潰锛岃€屼笉鏄浜屽瀹炵幇锛?4. 缁勪欢濡備綍鍦ㄥ崱鐗囥€佸垪琛ㄣ€佸鑸€佸脊灞傝繖浜涜澧冧腑淇濇寔缁熶竴锛?5. 濡備綍璁┾€滈€夋嫨鎬佲€濇垚涓鸿法鎺т欢瀹舵棌鐨勪竴鑷磋瑷€锛?
---

## 4. Checkbox / Radio 鐨勭洰鏍囨晥鏋?
### 4.1 Checkbox

- 灏哄锛?8 脳 18
- 鍑犱綍锛氬皬鍦嗚鏂瑰潡
- 榛樿鎬侊細鐧藉簳 + 缁嗚竟妗?- Hover锛氳竟妗嗘彁浜紝涓嶅仛澶稿紶鍙戝厜
- Checked锛氫富鑹插疄蹇冨簳锛屼絾淇濇寔鍏嬪埗锛屼笉鍋氶紦鑳€鏁堟灉
- Checkmark锛氭洿缁嗐€佹洿骞插噣锛岄伩鍏嶁€滃湡鈥濆拰鈥滅硦鈥?- Disabled锛氬け娲绘劅鏄庣‘锛屼絾涓嶈兘鑴忕伆

### 4.2 Radio

- 灏哄锛?8 脳 18
- 鍑犱綍锛氬鍦堣鏁淬€佸渾搴︾簿纭?- 榛樿鎬侊細鐧藉簳 + 缁嗚竟妗嗗渾鐜?- Hover锛氳竟妗嗘竻鏅版彁浜?- Checked锛氬鍦堜笌涓績鐐瑰叧绯绘槑纭紝涓績鐐逛笉鍋氳偉鍦?- 鐘舵€佽妭濂忥細鍜?Checkbox 淇濇寔涓€鑷?- Disabled锛氶噰鐢ㄤ笌 Checkbox 鍚屼竴濂楀け娲昏瑷€

### 4.3 鏂囨湰鍏崇郴

- 鎸囩ず鍣ㄤ笌鏂囧瓧闂磋窛缁熶竴
- 榛樿鏂囨湰涓嶆姠
- Checked 鍚庢暣浣撯€滄洿瀹屾暣鈥?- Disabled 鏂囨湰鏄け娲伙紝涓嶆槸鍙戣剰

---

## 5. 涓嶆槸鍙敼棰勮锛岃€屾槸鍋氬叡浜富棰樼郴缁?
杩欐鏄庣‘涓嶆帴鍙椾笅闈㈣繖绉嶅仛娉曪細

- preview 濂界湅锛屼絾鐪熷疄鐣岄潰杩樻槸鍙︿竴濂?- heading panel 鍗曠嫭鍐欎竴濂?QCheckBox 鏍峰紡
- gallery 閲屽仛涓存椂鏁堟灉锛宻hared 浣撶郴涓嶈惤鍦?
鏈蹇呴』婊¤冻锛?
1. 鍏变韩涓婚鏄湡婧?2. preview 鍙槸灞曠ず鍏变韩涓婚缁撴灉
3. 瀹為檯鐣岄潰鍜?preview 璧板悓涓€濂楁牱寮忕敓鎴愰€昏緫

---

## 6. 鎶€鏈惤鐐硅璁?
### 6.1 Theme 灞傦細鏂板閫夋嫨鎺т欢 token

鍦?`src/shared/ui/theme.py` 鐨?`AppTheme` 涓柊澧炰笓鐢?token銆?
寤鸿鎷嗘垚涓夌粍锛?
#### Checkbox token

- `checkbox_size`
- `checkbox_radius`
- `checkbox_border_width`
- `checkbox_border_color`
- `checkbox_hover_border_color`
- `checkbox_focus_border_color`
- `checkbox_bg`
- `checkbox_checked_bg`
- `checkbox_checked_border_color`
- `checkbox_checkmark_color`
- `checkbox_disabled_bg`
- `checkbox_disabled_border_color`
- `checkbox_disabled_checkmark_color`
- `checkbox_label_gap`

#### Radio token

- `radio_size`
- `radio_ring_width`
- `radio_border_color`
- `radio_hover_border_color`
- `radio_focus_border_color`
- `radio_bg`
- `radio_checked_ring_color`
- `radio_dot_size`
- `radio_dot_color`
- `radio_disabled_bg`
- `radio_disabled_border_color`
- `radio_disabled_dot_color`
- `radio_label_gap`

#### 閫夋嫨绫绘枃鏈?/ 鐘舵€?token

- `selection_label_color`
- `selection_label_checked_color`
- `selection_label_disabled_color`

璇存槑锛?
- Checkbox / Radio 鍒嗗紑寤?token锛屼笉鍏辩敤涓€涓ā绯婂瓧娈?- 浣嗗懡鍚嶈涔夊拰鐘舵€佽妭濂忎繚鎸佸钩琛岋紝鏂逛究浠ュ悗鎵╁睍鍒?Toggle / 閫変腑鎬佷綋绯?
### 6.2 Shared builder 灞?
寤鸿鏂板涓€涓?shared 閫夋嫨鎺т欢鏍峰紡 builder锛屼緥濡傦細

- `src/shared/ui/selection_control_style.py`

鎻愪緵鍑芥暟锛?
- `build_checkbox_stylesheet(theme, selector=...)`
- `build_radio_stylesheet(theme, selector=...)`

鎴栦竴灞傛暣鍚堬細

- `build_selection_control_stylesheet(theme, checkbox_selector=..., radio_selector=...)`

璁捐瑕佹眰锛?
1. 鑳界粰鐪熷疄鐣岄潰澶嶇敤
2. 鑳界粰 preview 澶嶇敤
3. 鑳界粰灞€閮?panel 閫氳繃 selector 绮惧噯鎸傝浇
4. 涓嶄緷璧?demo 绉佹湁瀹炵幇

### 6.3 鎸佺画浼樺寲鐨勭粨鏋勬敮鎸?
涓轰簡璁╁悗缁兘涓嶆柇鍚告敹寮€婧愪紭绉€浣撶郴鐨勬瀯寤烘柟寮忥紝杩欐璁捐涓嶅彧鍋氭牱寮忥紝杩樿涓衡€滄寔缁紭鍖栤€濋鐣欑粨鏋勶細

1. token 鍛藉悕蹇呴』鍙墿灞?
   - 涓嶈兘鍙湇鍔?Checkbox / Radio 褰撳墠涓€杞?   - 瑕佽兘鑷劧澶栨帹鍒?Toggle / 鍒楄〃閫変腑 / 瀵艰埅閫変腑

2. builder 蹇呴』鏄彲缁勫悎鐨?
   - 涓嶈鎶婃墍鏈夐€夋嫨鎺т欢鐘舵€佸啓姝诲湪鍗曚釜椤甸潰
   - 鍏佽涓嶅悓 selector / 涓嶅悓瀹瑰櫒璇澶嶇敤

3. preview 蹇呴』鎴愪负缁熶竴楠岃瘉闈?
   - gallery 涓兘骞舵帓灞曠ず default / hover / checked / disabled
   - 鍚庣画鍋氭í鍚戝姣旀椂锛岃兘蹇€熺湅鍒版垜浠殑宸窛鍦ㄥ摢閲?
4. panel 钀界偣蹇呴』鐪熷疄
   - `heading_numbering_styles.py` 鏄涓€鎵圭湡瀹炴帴鍏ョ偣
   - 閬垮厤鍙湪 gallery 閲岀湅璧锋潵鍏堣繘

---

## 7. 绗竴闃舵瀹炴柦鑼冨洿

绗竴闃舵鍙仛鏈€鏍稿績鐨勫叡浜寲锛屼笉鎵╂暎杩囧ご銆?
### 蹇呭仛

1. `AppTheme` 澧炲姞 checkbox / radio token
2. 鎶?shared checkbox / radio stylesheet builder
3. 娓呯悊 `heading_numbering_styles.py` 涓眬閮ㄥ啓姝荤殑 QCheckBox 鏍峰紡
4. 鎶?`demo_style_gallery.py` 鎺ュ埌鍚屼竴濂楀叡浜牱寮忎笂
5. 鎵撳紑棰勮鏍稿鏁堟灉

### 鏆備笉鍋?
1. 涓嶅湪杩欎竴杞噸鍋?ToggleSwitch 瑙嗚
2. 涓嶅湪杩欎竴杞噸鍋氭暣涓鑸綋绯?3. 涓嶅湪杩欎竴杞叏闈㈡敹鍙ｆ墍鏈?selected row / selected card

鍘熷洜锛?
- 褰撳墠鏈€閲嶈鐨勬槸鎶?Checkbox / Radio 鍋氭垚鍏变韩鐪熸簮
- 绗簩闃舵鍐嶆墿灞曞埌鈥滈€夋嫨鎺т欢瀹舵棌鈥?
---

## 8. 绗簩闃舵鎵╁睍鏂瑰悜

鍦?Checkbox / Radio 绋冲畾鍚庯紝缁х画缁熶竴锛?
### 8.1 Toggle / Segmented / Preset 绫?
- `toggle_switch.py`
- heading panel 閲岀殑妯″紡鍒囨崲鎸夐挳
- 棰勮鍒囨崲 / 杞婚噺 segmented button

鐩爣锛?
- 璁┾€滃紑鍏?/ 鍗曢€?/ 妯″紡鍒囨崲鈥濈殑鐘舵€佽妭濂忓悓婧?
### 8.2 鍒楄〃涓庡鑸€変腑鎬?
- 宸︿晶瀵艰埅閫変腑椤?- 鍒楄〃閫変腑琛?- 鍗＄墖閫変腑鎬?- 棰勮鍒楄〃閫変腑鎬?
鐩爣锛?
- 璁┾€滈€変腑鈥濈殑琛ㄨ揪鍦ㄦ暣涓骇鍝侀噷涓€鑷?
### 8.3 鏇村畬鏁寸殑閫夋嫨鎺т欢璇█

鏈€缁堝仛鍒帮細

- Checkbox
- Radio
- Toggle
- List selection
- Sidebar selection
- Card selection

閮借兘琚劅鐭ヤ负鍚屼竴浠ｄ骇鍝?
---

## 9. 瀹炴柦椤哄簭寤鸿

鍦ㄥ師鏈夊垎闃舵鍩虹涓婏紝澧炲姞涓€鏉¤疮绌垮紡鏈哄埗锛?
> **姣忎竴闃舵閮借鍋氫竴娆℃í鍚戝鏍囧鏍?*

### Phase 1锛氬畾涔夐€夋嫨鎺т欢璇█

鐩爣锛?
- 鏄庣‘鍑犱綍銆佺姸鎬併€佹枃鏈叧绯汇€乨isabled 璇箟

浜у嚭锛?
- 鏂?token 璁捐
- 鐘舵€佽鍒?- 瑙嗚鏍囧昂
- 绗竴鐗堝閮ㄥ鏍囨憳瑕侊紙鎴戜滑瀛︿粈涔堬紝涓嶅浠€涔堬級

### Phase 2锛氳惤 shared 涓婚灞?
鐩爣锛?
- 鍦?`AppTheme` 鍜?shared builder 涓舰鎴愭寮忚兘鍔?
浜у嚭锛?
- checkbox / radio token
- stylesheet builder
- 鍙敤浜庢í鍚戝姣旂殑 preview 灞曠ず闈?
### Phase 3锛氭浛鎹㈢湡瀹炶惤鐐?
椤哄簭寤鸿锛?
1. `heading_numbering_styles.py`
2. `demo_style_gallery.py`
3. 鍚庣画鐪熷疄鐣岄潰涓殑鍏跺畠 Checkbox / Radio

### Phase 4锛氭墿灞曚负閫夋嫨瀹舵棌

鐩爣锛?
- 灏嗗悓涓€璇郴鎵╁睍鍒?Toggle / 瀵艰埅 / 閫変腑鍒楄〃

骞朵笖鍦ㄨ繖涓€闃舵寮€濮嬫妸鈥滆法瀹瑰櫒璇鈥濈撼鍏ョ粺涓€锛?
- 鍗＄墖璇
- 鍒楄〃璇
- 瀵艰埅璇
- 琛ㄥ崟璇

### Phase 5锛氬儚绱犵骇寰皟

閲嶇偣妫€鏌ワ細

- 鍕剧嚎绮楃粏
- 鍦嗙偣澶у皬
- 1px 杈规鏄惁鍙戣櫄
- hover 鏄惁澶急
- disabled 鏄惁鍙戣剰
- 鎸囩ず鍣ㄤ笌鏂囧瓧瀵归綈鏄惁绮惧噯

---

## 10. 楠屾敹鏍囧噯

绗竴闃舵瀹屾垚鍚庯紝蹇呴』婊¤冻锛?
1. Checkbox / Radio 宸叉湁鐙珛 theme token
2. shared builder 宸插瓨鍦紝涓?preview / real panel 鍏辩敤
3. `heading_numbering_styles.py` 涓嶅啀鍋峰伔缁存姢涓€濂楃嫭绔?QCheckBox 瑙嗚璇█
4. preview 鐨勬晥鏋滆兘绋冲畾澶嶇幇鍒扮湡瀹炵晫闈?5. Checkbox / Radio 鐨勭姸鎬佽瑷€涓€鑷?6. disabled 鎬佹槸澶辨椿锛屼笉鏄剰鐏?7. 鏁翠綋椋庢牸涓庣幇鏈夋寜閽綋绯讳笉鍐茬獊
8. preview 鑳芥敮鎸佸悗缁í鍚戝姣旓紝鑰屼笉鏄彧鑳介潤鎬佺湅鍗曚竴鏁堟灉
9. 鏂规鏂囨。涓繚鐣欌€滃弬鑰冧綋绯?鈫?杞瘧缁撴灉鈥濈殑鏄犲皠鍏崇郴

---

## 11. 椋庨櫓涓庢帶鍒?
### 椋庨櫓 1锛氬彧鎶?preview 鍋氬ソ鐪?
鎺у埗锛?
- 鍏变韩 builder 鍏堣
- preview 鍙秷璐?shared 缁撴灉

### 椋庨櫓 2锛欳heckbox / Radio 鍋氬ソ浜嗭紝浣嗗拰 Toggle / 瀵艰埅鑴辫妭

鎺у埗锛?
- 杩欐灏辨妸瀹冨畾涔夋垚鈥滈€夋嫨鎺т欢瀹舵棌绗竴闃舵鈥?- token 鍛藉悕涓庣姸鎬佽璁′负鍚庣画鎵╁睍鐣欏彛

### 椋庨櫓 3锛氬仛寰楀お绉€姘旓紝鐘舵€佷笉娓呮

鎺у埗锛?
- 閲囩敤鏌斿拰娣峰悎鐗堬紝鑰屼笉鏄亸 macOS 绾交閲忔柟妗?- 閫変腑鎬佸繀椤绘瘮 macOS 鏇存竻妤?
### 椋庨櫓 4锛氬仛寰楀お浜紝鐮村潖鏁翠綋鍏嬪埗鎰?
鎺у埗锛?
- 閬垮厤 Fluent 寮忓ぇ闈㈢Н楂樹寒
- hover / checked 鑺傚瑕佹敹浣?
### 椋庨櫓 5锛氭í鍚戝鏍囨渶鍚庡彉鎴愭妱琚垨璁稿彲璇佹薄鏌?
鎺у埗锛?
- 澶栭儴浣撶郴鍙涔犺璁＄粨鏋勩€佺姸鎬佺粍缁囥€佸睍绀烘柟娉?- 涓嶇洿鎺ュ鍒剁涓夋柟鍙楅檺浠ｇ爜銆佽祫婧愩€佸浘鏍囨垨鏍峰紡鐗囨
- 褰撳墠 MIT 婧愮爜浠撳簱鍙繚鐣欒嚜鐮斿疄鐜?
### 椋庨櫓 6锛氫笉鏂弬鑰冨閮ㄤ綋绯伙紝鍙嶈€岃鍐呴儴椋庢牸鍙戞暎

鎺у埗锛?
- 鎵€鏈夊閮ㄨ緭鍏ラ兘蹇呴』杞瘧鍥炵粺涓€鐨?`AppTheme + shared builder` 浣撶郴
- 涓嶅厑璁稿洜涓衡€滄煇搴撴煇椤甸潰寰堝ソ鐪嬧€濆氨鍗曠偣寮€鍙ｅ瓙

---

## 11.1 鎸佺画浼樺寲宸ヤ綔娴?
鍚庣画姣忚疆浼樺寲锛屽缓璁浐瀹氶噰鐢ㄤ互涓嬪惊鐜細

1. 閫変竴涓鏃忛棶棰?
   - 渚嬪 Checkbox / Radio / Toggle / Sidebar selection

2. 鍋氫竴娆℃í鍚戝鏍?
   - 鐪嬪紑婧愪紭绉€浣撶郴鎬庝箞鍋氬嚑浣曘€佺姸鎬併€佸鍣ㄥ叧绯汇€佸睍绀洪潰

3. 鎻愬彇鍘熷垯
   - 鍐欏嚭鈥滄垜浠€熼壌浠€涔堬紝涓嶅€熼壌浠€涔堚€?
4. 杞瘧涓哄唴閮ㄧ郴缁?
   - 钀藉埌 token / builder / preview / 鐪熷疄 panel

5. 鎵撳紑棰勮
   - 鐪嬫槸鍚︽瘮涓婁竴杞洿瀹屾暣

6. 鍥炲埌鐪熷疄鐣岄潰
   - 纭涓嶆槸鍙湪 gallery 鎴愮珛

---

## 12. 鏈€缁堝喅绛?
鏈鈥滀笅涓€浠?UI 浼樺寲鏂规鈥濈殑绗竴鍧楀湴鍩猴紝涓嶆槸鍏ㄧ洏閲嶅仛锛岃€屾槸锛?
> 浠?**鏌斿拰娣峰悎鐗?2.0** 涓鸿瑙夋柟鍚戯紝鍏堟妸 Checkbox / Radio 鍋氭垚鍏变韩涓婚绯荤粺锛屽啀鍚戞暣涓€夋嫨鎺т欢瀹舵棌鎵╁睍銆?
杩欐槸涓€涓樁娈靛寲浜у搧鏂规锛屼笉鏄眬閮ㄨˉ涓併€?
Checkbox / Radio 鏄涓€闃舵鐨勫叆鍙ｏ紝浣嗙粓鐐规槸鏁村 Selection Controls 瑙嗚璇█銆?
骞朵笖杩欏鏂规浼氭寔缁帴鍙楀紑婧愪紭绉€鎺т欢瀹舵棌鐨勬í鍚戣緭鍏ワ紝浣嗘墍鏈夎緭鍏ラ兘蹇呴』缁忚繃锛?
> **鍙傝€?鈫?鎻愮偧 鈫?杞瘧 鈫?鍏变韩鍖?鈫?棰勮楠岃瘉 鈫?鐪熷疄鐣岄潰楠岃瘉**

鑰屼笉鏄洿鎺ョ収鎼€?
---

## 13. 鍙傝€冩潵婧愶紙鐢ㄤ簬鏂规硶瀵规爣锛屼笉浣滀负浠ｇ爜寮曞叆锛?
- Libadwaita Style Classes
  https://gnome.pages.gitlab.gnome.org/libadwaita/doc/1.6/style-classes.html
- Libadwaita Adaptive Layouts
  https://gnome.pages.gitlab.gnome.org/libadwaita/doc/main/adaptive-layouts.html
- KDE Kirigami Controls and Interactive Elements
  https://develop.kde.org/docs/getting-started/kirigami/components-controls/
- PyQt-Fluent-Widgets Repository
  https://github.com/zhiyiYo/PyQt-Fluent-Widgets
