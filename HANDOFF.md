项目名称：video-automation-tool（竖屏短视频内容工厂，工业品牌：Siglen / Fareo）

目标：
- 把“创意 → 拍摄 → 剪辑 → 输出”变成可重复、可扩展的生产线
- 创意脚本（Creative Script）人/甲方/AI可读；生产脚本（Production Script）机器可跑
- 输出拍摄指南降低废片率，并用导演规则（director_engine）保证风格一致

当前已建成的结构/能力（已跑通）：
1) main.py 提供 CLI：run / compile / guide（支持从 creative 生成 production，再运行）【main.py 已存在】。
2) run.sh 作为单开关面板（MODE=run/compile/guide/creative/clean-tts），并设置 TTS 环境变量（AI302_AZURE_TTS_URL、TTS_HTTP_PROXY）【run.sh 已存在】。
3) creative/compiler.py：Creative Script → Production Script（compiled.yaml）。当前逻辑较保守，visual 会落到 notes，source 默认 next:tags:...。
4) shooting/guide_generator.py：Creative Script → shooting_guide.json（required_shots + coverage + duration_range）。
5) director_engine：已实现 pacing / ending / transitions / repetition 规则模块；profile 有 content_factory（可靠工业风）。
6) utils.py 为稳定主管线：递归扫描素材池，按 DSL timeline 选素材、拼接、导出 tmp mp4、导出 timeline json/srt；BGM 可缺省；字幕烧录用 ffmpeg libass。
7) 已跑通 test_run_v1：guide.json 生成成功，compile 生成 compiled.yaml 成功，run 生成最终 mp4 成功（当 SRT 不可用会自动跳过烧字幕）。

本次实战测试产物：
- test_run_v1.shooting_guide.json（4 个任务：establish_context / show_capability / build_trust / brand_close）
- test_run_v1.compiled.yaml（已手工升级为段内结构：wide→medium→detail→hero）
- Siglen_compiled.mp4 输出成功；若无 VO events 则跳过 burn_subtitles，输出无字幕版供剪映做广告字。

关键经验/坑：
- MaterialPicker 递归搜集视频时曾因扩展名大小写（.MOV/.MP4）导致 pool 过小，造成素材循环；需用 suffix.lower() 判断扩展名或确保 glob 不区分大小写。
- burn_subtitles_ffmpeg 会因 timeline.srt 不存在/为空导致 ffmpeg 报错，因此加入“srt 存在且非空才烧字幕，否则跳过”保护。
- INPUT_DIR 推荐限定到 brand/factory 子目录避免误抽未整理素材（_INBOX/_WORKING）。
- 新导演需求：段内叙事（automation 段必须 wide→medium→detail），不能只靠阶段抽一条；现阶段通过手改 compiled.yaml 实现。
- 新需求待做：统一画布适配（避免部分素材黑边）、让 compiler 自动输出段内结构、guide 同时输出 md 任务清单 + rename_plan.txt。

当前目录（用户描述）：
- scripts/Siglen & scripts/Fareo 子文件夹
- input_videos & output_videos 各自按 Siglen/Fareo 分子文件夹（镜像在移动硬盘 /VideoAutomation/...）
- assets/audio raw processed；creative_scripts 与 scripts 平行；.venv 为 Python 环境

命名规范（v1）：
scene_content_coverage_move_index.(mp4/mov)
move 词典：static, panL/panR, tiltU/tiltD, slideL/slideR, pushin, pullout, follow, pov, orbit, reveal, expand
hero 镜头用于开场/收尾/Logo露出，如 factory_building_hero_orbit_01