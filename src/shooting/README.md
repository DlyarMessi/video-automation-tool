# Shooting System

The shooting system ensures that captured footage
is usable, consistent, and predictable.

Goals:
- Reduce unusable footage
- Ensure coverage for automated editing
- Enable repeatable shooting standards

This system defines:
- Shot requirements
- Coverage expectations
- Asset categorization

It does NOT:
- Teach cinematography
- Decide creative direction

# Project Lexicon v1 (VideoAutomation)

## 1) Shot Size / Coverage (景别/用途)
- wide: 环境/空间建立（站远一点，能看出“在哪”）
- medium: 主体行为（主体占画面 60–80%，还能看到一点环境）
- detail: 细节可信度（按钮/材质/机械动作/读数等）
- hero: 品牌级镜头（可安全用于开场/收尾/Welcome/Logo露出）

## 2) Movement / Move Tokens (运镜词条)
### 基础运镜（v1 统一拼写）
- static: 静止镜头
- panL / panR: 左右摇摄（原地转动）
- tiltU / tiltD: 上下摇摄（原地抬头/低头）  ← 注意：上下叫 tilt，不叫 pan
- slideL / slideR: 平移（相机整体左右移动，有视差）
- pushin: 推进（相机靠近主体）
- pullout: 拉远（相机远离主体）
- follow: 跟随主体运动（第三人称跟拍）
- pov: 主观视角（像“我的眼睛在走/在看”）

### 创意/高级运镜（允许出现，不会破坏系统）
- orbit: 围绕主体环绕（常用于航拍/品牌空间）
- reveal: 揭示/开门/遮挡物移开后的露出
- expand: 空间扩张感/旋转+后退的冲击（你提到的“盗梦空间感”）

## 3) Naming Convention (命名规范 v1)
<scene>_<content>_<coverage>_<move>_<index>.ext

Examples:
- factory_building_hero_orbit_01.mp4
- factory_entrance_hero_reveal_01.mp4
- factory_testing_detail_static_02.mov
- showroom_logo_hero_static_01.mp4

Index rule:
- 只有在 scene+content+coverage+move 都相同的情况下才累加 01/02/03
- 任意字段变化都重置为 01
