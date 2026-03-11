from __future__ import annotations
import os
import subprocess
from pathlib import Path

def run(cmd: list[str], cwd: Path):
    print("RUN:", " ".join(cmd))
    subprocess.run(cmd, cwd=str(cwd), check=True)

def main():
    # 你把 VideoLingo 仓库路径放到环境变量，避免写死
    vl_home = os.environ.get("VIDEOLINGO_HOME", "").strip()
    if not vl_home:
        raise RuntimeError("请先设置环境变量 VIDEOLINGO_HOME=/path/to/VideoLingo")

    vl = Path(vl_home).expanduser().resolve()
    if not vl.exists():
        raise RuntimeError(f"VIDEOLINGO_HOME 路径不存在: {vl}")

    # 输入
    in_video = Path(os.environ.get("VL_IN_VIDEO", "input.mp4")).resolve()
    in_srt = Path(os.environ.get("VL_IN_SRT", "captions.srt")).resolve()
    out_dir = Path(os.environ.get("VL_OUT_DIR", "vl_out")).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    # ⚠️ 这里不臆造 VideoLingo 每个脚本的参数（不同版本可能不同）
    # 正确做法：先让你在 VideoLingo 仓库内对每一步脚本执行 `-h` 查看参数
    # DeepWiki 显示配音链路模块：_8_1_audio_task.py / _10_gen_audio.py / _11_merge_audio.py / _12_dub_to_vid.py [2](https://api.asm.skype.com/v1/objects/0-ea-d1-e3fef8568ef7906ba5bc4f7f07a431aa/views/original/utils.py)

    # 示例：你可以先在 VideoLingo 目录手动跑：
    # python core/_8_1_audio_task.py -h
    # python core/_10_gen_audio.py -h
    # 然后把正确参数填到下面 run(...) 里

    print("Video:", in_video)
    print("SRT:", in_srt)
    print("Out:", out_dir)
    print("下一步：在 VideoLingo 目录分别运行 'python core/_8_1_audio_task.py -h' 等，确认参数后填入本脚本。")

if __name__ == "__main__":
    main()
    