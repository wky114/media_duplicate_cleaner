import os
import sys
from collections import defaultdict
import re
import random
import subprocess
from datetime import datetime
import json
import tkinter as tk
from tkinter import filedialog

# 检查Pillow库
try:
    from PIL import Image
except ImportError:
    import subprocess
    import sys
    print("未检测到Pillow库，正在自动安装...")
    subprocess.check_call([sys.executable, '-m', 'pip', 'install', 'Pillow'])
    from PIL import Image


def get_video_info(video_path):
    """获取视频的元数据信息，包括时长和帧率"""
    if not os.path.exists(video_path):
        return None
    
    try:
        cmd = [
            'ffprobe',
            '-v', 'quiet',
            '-select_streams', 'v:0',
            '-show_entries', 'stream=duration,r_frame_rate',
            '-of', 'json',
            video_path
        ]
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if result.returncode != 0:
            return None
            
        # 使用json.loads替代eval，更安全
        info = json.loads(result.stdout)
        stream = info.get('streams', [{}])[0]
        
        duration = stream.get('duration')
        if duration is None:
            return None
        duration = float(duration)
        
        frame_rate_str = stream.get('r_frame_rate', '0/1')
        try:
            num, denom = map(int, frame_rate_str.split('/'))
            frame_rate = num / denom if denom != 0 else 0
        except (ValueError, ZeroDivisionError):
            frame_rate = 0
            
        return {
            'duration': duration,
            'frame_rate': frame_rate
        }
    except Exception as e:
        print(f"获取视频信息时出错 {video_path}: {e}")
        return None



def find_best_file_to_keep(files, video_metadata):
    """智能选择要保留的文件，而不是随机选择"""
    if not files:
        return None
    
    # 对于视频文件，优先保留：
    # 1. 文件名最短的（通常是原始文件）
    # 2. 修改时间最早的
    # 3. 如果都相同，则选择第一个
    
    def file_priority(file_path):
        filename = os.path.basename(file_path)
        # 检查是否包含数字后缀（表示是副本）
        has_copy_suffix = bool(re.search(r'[（(]\d+[）)]', filename))
        # 获取文件修改时间
        try:
            mtime = os.path.getmtime(file_path)
        except:
            mtime = float('inf')
        
        # 返回排序优先级（越小越优先）
        return (has_copy_suffix, len(filename), mtime)
    
    return min(files, key=file_priority)

def process_directory(directory, log_file):
    VIDEO_EXTENSIONS = {'.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv', '.webm'}
    IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp'}
    image_files = []
    video_files = []
    try:
        for filename in os.listdir(directory):
            full_path = os.path.join(directory, filename)
            if os.path.isfile(full_path):
                ext = os.path.splitext(filename)[1].lower()
                if ext in IMAGE_EXTENSIONS:
                    image_files.append(full_path)
                elif ext in VIDEO_EXTENSIONS:
                    video_files.append(full_path)
    except PermissionError:
        print(f"权限不足，跳过目录: {directory}")
        return {}, {}, {}, {}
    # 1. 图片分辨率+字节大小去重分组
    image_groups = {}
    image_metadata = {}
    for file in image_files:
        try:
            size = os.path.getsize(file)
            with Image.open(file) as img:
                width, height = img.size
            key = (size, width, height)
            if key not in image_groups:
                image_groups[key] = []
            image_groups[key].append(file)
            image_metadata[file] = {'size': size, 'width': width, 'height': height}
        except Exception as e:
            print(f"读取图片信息失败: {file}, 错误: {e}")
            continue
    image_duplicate_groups = []
    for key, files in image_groups.items():
        if len(files) > 1:
            file_to_keep = min(files, key=lambda x: (len(os.path.basename(x)), os.path.getmtime(x)))
            files_to_delete = [f for f in files if f != file_to_keep]
            image_duplicate_groups.append({'key': key, 'keep': file_to_keep, 'delete': files_to_delete})
    # 2. 图片副本分组
    image_number_pattern = re.compile(r'^(.*?)[（(](\d+)[）)]$')
    image_copies_groups = defaultdict(lambda: {'origin': None, 'copies': []})
    for file in image_files:
        name = os.path.splitext(os.path.basename(file))[0]
        match = image_number_pattern.match(name)
        if match:
            base_name = match.group(1)
            original_file = os.path.join(directory, f"{base_name}{os.path.splitext(file)[1]}")
            image_copies_groups[original_file]['origin'] = original_file
            image_copies_groups[original_file]['copies'].append(file)
    # 只保留有副本的分组
    image_copies_groups = [v for v in image_copies_groups.values() if v['origin'] and v['copies']]
    # 3. 同名图片与视频分组
    all_files = image_files + video_files
    name_groups = defaultdict(list)
    for file in all_files:
        base_name = os.path.splitext(os.path.basename(file))[0]
        name_groups[base_name].append(file)
    same_name_groups = []
    for files in name_groups.values():
        has_video = any(os.path.splitext(f)[1].lower() in VIDEO_EXTENSIONS for f in files)
        has_image = any(os.path.splitext(f)[1].lower() in IMAGE_EXTENSIONS for f in files)
        if has_video and has_image:
            group = {'videos': [f for f in files if os.path.splitext(f)[1].lower() in VIDEO_EXTENSIONS],
                     'images': [f for f in files if os.path.splitext(f)[1].lower() in IMAGE_EXTENSIONS]}
            same_name_groups.append(group)
    # 4. 视频去重分组
    video_groups = defaultdict(list)
    video_metadata = {}
    for file in video_files:
        try:
            size_mb = round(os.path.getsize(file) / (1024 * 1024), 2)
            metadata = get_video_info(file)
            if metadata:
                key = (
                    size_mb,
                    round(metadata['duration'], 2),
                    round(metadata['frame_rate'], 2)
                )
                video_groups[key].append(file)
                video_metadata[file] = {
                    'size_mb': size_mb,
                    'duration': metadata['duration'],
                    'frame_rate': metadata['frame_rate']
                }
            else:
                key = (size_mb, None, None)
                video_groups[key].append(file)
                video_metadata[file] = {
                    'size_mb': size_mb,
                    'duration': None,
                    'frame_rate': None
                }
        except Exception as e:
            print(f"处理视频文件时出错 {file}: {e}")
            continue
    video_duplicate_groups = []
    for key, files in video_groups.items():
        if len(files) > 1:
            file_to_keep = find_best_file_to_keep(files, video_metadata)
            files_to_delete = [f for f in files if f != file_to_keep]
            video_duplicate_groups.append({'key': key, 'keep': file_to_keep, 'delete': files_to_delete})
    return image_duplicate_groups, image_copies_groups, same_name_groups, video_duplicate_groups

def main():
    root = tk.Tk()
    root.withdraw()
    root_directory = filedialog.askdirectory(title="请选择要处理的根目录")
    if not root_directory:
        print("未选择目录，程序已退出。"); return
    if not os.path.isdir(root_directory):
        print(f"错误: 目录 '{root_directory}' 不存在")
        return
    print(f"开始处理目录: {root_directory}")
    log_file = os.path.join(os.getcwd(), f"delete_operation_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
    try:
        with open(log_file, 'w', encoding='utf-8') as f:
            f.write(f"开始时间: {datetime.now()}\n")
            f.write(f"根目录: {root_directory}\n\n")
    except Exception as e:
        print(f"无法创建日志文件: {e}")
        sys.exit(1)
    processed_dirs = 0
    # 四类分组全局收集
    all_image_duplicate_groups = []
    all_image_copies_groups = []
    all_same_name_groups = []
    all_video_duplicate_groups = []
    for root, dirs, files in os.walk(root_directory):
        has_media = any(
            os.path.splitext(f)[1].lower() in {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', 
                                              '.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv', '.webm'}
            for f in files
        )
        if has_media:
            processed_dirs += 1
            print(f"\r扫描目录: {processed_dirs}", end='', flush=True)
            image_duplicate_groups, image_copies_groups, same_name_groups, video_duplicate_groups = process_directory(root, log_file)
            if image_duplicate_groups:
                all_image_duplicate_groups.extend([{'dir': root, **g} for g in image_duplicate_groups])
            if image_copies_groups:
                all_image_copies_groups.extend([{'dir': root, **g} for g in image_copies_groups])
            if same_name_groups:
                all_same_name_groups.extend([{'dir': root, **g} for g in same_name_groups])
            if video_duplicate_groups:
                all_video_duplicate_groups.extend([{'dir': root, **g} for g in video_duplicate_groups])
    print()  # 换行

    # 显示功能组统计信息
    print("\n=== 功能组执行情况 ===")
    print(f"1. 图片分辨率+字节大小去重组: {len(all_image_duplicate_groups)} 组")
    print(f"2. 图片副本去重组: {len(all_image_copies_groups)} 组")
    print(f"3. 同名图片与视频清理组: {len(all_same_name_groups)} 组")
    print(f"4. 视频去重组: {len(all_video_duplicate_groups)} 组")
    print("=====================\n")

    # 1. 图片分辨率+字节大小去重组
    print("\n【图片分辨率+字节大小去重组】")
    if all_image_duplicate_groups:
        for idx, group in enumerate(all_image_duplicate_groups, 1):
            key, keep_file, del_files, directory = group['key'], group['keep'], group['delete'], group['dir']
            print(f"\n目录: {directory}")
            print(f"分组{idx}: 大小={key[0]}字节, 分辨率={key[1]}x{key[2]}")
            print(f"  保留: {keep_file}")
            print(f"  待删除:")
            for f in del_files:
                print(f"    {f}")
        resp = input("是否删除本组所有待删除图片？(y/N): ").strip().lower()
        if resp == 'y':
            for group in all_image_duplicate_groups:
                for file in group['delete']:
                    try:
                        os.remove(file)
                        print(f"已删除: {file}")
                        with open(log_file, 'a', encoding='utf-8') as f:
                            f.write(f"图片分辨率去重已删除: {file}\n")
                    except Exception as e:
                        print(f"删除失败: {file}, 错误: {e}")
                        with open(log_file, 'a', encoding='utf-8') as f:
                            f.write(f"图片分辨率去重删除失败: {file}, 错误: {e}\n")
        else:
            print("已跳过本组图片的删除。")
    else:
        print("本组无需要处理的数据。")

    # 2. 图片副本去重组
    print("\n【图片副本去重组】")
    if all_image_copies_groups:
        for idx, group in enumerate(all_image_copies_groups, 1):
            directory = group['dir']
            origin = group['origin']
            copies = group['copies']
            print(f"\n目录: {directory}")
            print(f"分组{idx}: 原图: {origin}")
            print(f"  副本:")
            for f in copies:
                print(f"    {f}")
        resp = input("是否删除本组所有图片副本？(y/N): ").strip().lower()
        if resp == 'y':
            for group in all_image_copies_groups:
                for file in group['copies']:
                    try:
                        os.remove(file)
                        print(f"已删除: {file}")
                        with open(log_file, 'a', encoding='utf-8') as f:
                            f.write(f"图片副本已删除: {file}\n")
                    except Exception as e:
                        print(f"删除失败: {file}, 错误: {e}")
                        with open(log_file, 'a', encoding='utf-8') as f:
                            f.write(f"图片副本删除失败: {file}, 错误: {e}\n")
        else:
            print("已跳过本组图片副本的删除。")
    else:
        print("本组无需要处理的数据。")

    # 3. 同名图片与视频清理组
    print("\n【同名图片与视频清理组】")
    if all_same_name_groups:
        for idx, group in enumerate(all_same_name_groups, 1):
            directory = group['dir']
            videos = group['videos']
            images = group['images']
            print(f"\n目录: {directory}")
            print(f"分组{idx}: ")
            print(f"  视频:")
            for v in videos:
                print(f"    {v}")
            print(f"  图片:")
            for i in images:
                print(f"    {i}")
        resp = input("是否删除本组所有与视频同名的图片？(y/N): ").strip().lower()
        if resp == 'y':
            for group in all_same_name_groups:
                for file in group['images']:
                    try:
                        os.remove(file)
                        print(f"已删除: {file}")
                        with open(log_file, 'a', encoding='utf-8') as f:
                            f.write(f"同名图片已删除: {file}\n")
                    except Exception as e:
                        print(f"删除失败: {file}, 错误: {e}")
                        with open(log_file, 'a', encoding='utf-8') as f:
                            f.write(f"同名图片删除失败: {file}, 错误: {e}\n")
        else:
            print("已跳过本组同名图片的删除。")
    else:
        print("本组无需要处理的数据。")

    # 4. 视频去重组
    print("\n【视频去重组】")
    if all_video_duplicate_groups:
        for idx, group in enumerate(all_video_duplicate_groups, 1):
            key, keep_file, del_files, directory = group['key'], group['keep'], group['delete'], group['dir']
            print(f"\n目录: {directory}")
            print(f"分组{idx}: 大小={key[0]}MB, 时长={key[1]}s, 帧率={key[2]}fps")
            print(f"  保留: {keep_file}")
            print(f"  待删除:")
            for f in del_files:
                print(f"    {f}")
        resp = input("是否删除本组所有待删除视频？(y/N): ").strip().lower()
        if resp == 'y':
            for group in all_video_duplicate_groups:
                for file in group['delete']:
                    try:
                        os.remove(file)
                        print(f"已删除: {file}")
                        with open(log_file, 'a', encoding='utf-8') as f:
                            f.write(f"视频去重已删除: {file}\n")
                    except Exception as e:
                        print(f"删除失败: {file}, 错误: {e}")
                        with open(log_file, 'a', encoding='utf-8') as f:
                            f.write(f"视频去重删除失败: {file}, 错误: {e}\n")
        else:
            print("已跳过本组视频的删除。")
    else:
        print("本组无需要处理的数据。")

    # 显示结束图案和感谢语
    print("\n" + "="*50)
    print("""
    /\\___/\\
   (  o o  )
   (  =^=  ) 
    (____)__)
    
    感谢使用本脚本，请投喂~
    """)
    print("="*50 + "\n")

if __name__ == "__main__":
    main() 