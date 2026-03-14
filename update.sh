#!/bin/bash

# 更新之前，先确保工作区是干净的
git status

# 更新包1：新增功能包、模块更新等
echo "开始更新功能包"

# 更新包2：修改pool_plan.yaml、增加task_card功能等
echo "更新 task_card 功能"

# 更新包3：更新 slug 生成与 director_engine 引擎
echo "更新 slug 生成和 director_engine"

# 提交更新
git add .
git commit -m "更新功能：引入任务卡片生成、slug生成和导演引擎更新"
git push origin main

echo "更新完成并推送"