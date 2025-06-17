import os
import sys
from collections import defaultdict
import re
import random
import subprocess
from datetime import datetime
import json
import webbrowser


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
    """处理单个目录，收集要删除的文件及其详细信息"""
    VIDEO_EXTENSIONS = {'.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv', '.webm'}
    IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp'}
    
    # 初始化处理状态
    processing_status = {
        'image_processing': {
            'total_files': 0,
            'duplicate_groups': 0,
            'files_to_delete': 0,
            'status': '未处理'
        },
        'video_processing': {
            'total_files': 0,
            'duplicate_groups': 0,
            'files_to_delete': 0,
            'status': '未处理'
        }
    }
    
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
        return [], {}, processing_status
    
    # 更新图片处理状态
    processing_status['image_processing']['total_files'] = len(image_files)
    processing_status['image_processing']['status'] = '处理中'
    
    # 处理图片文件
    image_number_pattern = re.compile(r'^(.*?)[（(](\d+)[）)]$')
    image_numbered_files_to_delete = []
    image_groups = defaultdict(list)
    
    # 收集按编号分组的图片
    for file in image_files:
        name = os.path.splitext(os.path.basename(file))[0]
        ext = os.path.splitext(file)[1]
        match = image_number_pattern.match(name)
        if match:
            base_name = match.group(1)
            original_file = os.path.join(directory, f"{base_name}{ext}")
            if original_file in image_files:
                key = (base_name, ext)
                if original_file not in image_groups[key]:
                    image_groups[key].append(original_file)
                image_groups[key].append(file)
                image_numbered_files_to_delete.append(file)
    
    # 更新图片处理状态
    processing_status['image_processing']['duplicate_groups'] = len(image_groups)
    processing_status['image_processing']['files_to_delete'] = len(image_numbered_files_to_delete)
    processing_status['image_processing']['status'] = '已完成'
    
    # 更新视频处理状态
    processing_status['video_processing']['total_files'] = len(video_files)
    processing_status['video_processing']['status'] = '处理中'
    
    # 处理视频文件 - 通过ffmpeg提取的数据检测重复
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
                # 如果无法获取元数据，只按大小分组
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
    
    # 确定要删除的视频文件
    video_files_to_delete = []
    kept_files = []
    
    # 只保留有重复的组
    video_groups = {k: v for k, v in video_groups.items() if len(v) > 1}
    
    for key, files in video_groups.items():
        if len(files) > 1:
            file_to_keep = find_best_file_to_keep(files, video_metadata)
            files_to_delete = [f for f in files if f != file_to_keep]
            video_files_to_delete.extend(files_to_delete)
            kept_files.append(file_to_keep)
    
    # 更新视频处理状态
    processing_status['video_processing']['duplicate_groups'] = len(video_groups)
    processing_status['video_processing']['files_to_delete'] = len(video_files_to_delete)
    processing_status['video_processing']['status'] = '已完成'
    
    # 合并需要删除的文件
    files_to_delete = list(set(image_numbered_files_to_delete + video_files_to_delete))
    
    # 构建删除文件的详细信息
    files_to_delete_info = []
    
    for file in files_to_delete:
        try:
            if file in video_metadata:
                meta = video_metadata[file]
                duration_str = f"{meta['duration']:.2f}s" if meta['duration'] is not None else "未知"
                fps_str = f"{meta['frame_rate']:.2f}fps" if meta['frame_rate'] is not None else "未知"
                info = {
                    'path': file,
                    'type': 'video',
                    'details': f"{os.path.basename(file)} (视频: {meta['size_mb']:.2f}MB, {duration_str}, {fps_str})"
                }
            else:
                size_mb = round(os.path.getsize(file) / (1024 * 1024), 2)
                info = {
                    'path': file,
                    'type': 'image', 
                    'details': f"{os.path.basename(file)} (图片: {size_mb:.2f}MB)"
                }
            files_to_delete_info.append(info)
        except Exception as e:
            print(f"处理文件信息时出错 {file}: {e}")
            continue
    
    # 记录到日志文件
    try:
        with open(log_file, 'a', encoding='utf-8') as f:
            f.write(f"\n目录: {directory}\n")
            f.write(f"总图片数: {len(image_files)}, 总视频数: {len(video_files)}\n")
            f.write(f"待删除文件数: {len(files_to_delete_info)}\n")
            
            if video_files_to_delete:
                f.write("\n视频分组删除详情:\n")
                for key, files in video_groups.items():
                    if len(files) > 1:
                        file_to_keep = find_best_file_to_keep(files, video_metadata)
                        files_to_delete_in_group = [f for f in files if f != file_to_keep]
                        
                        f.write(f"- 重复组 (共{len(files)}个文件):\n")
                        f.write(f"  保留: {os.path.basename(file_to_keep)}\n")
                        f.write(f"  删除: {', '.join(os.path.basename(f) for f in files_to_delete_in_group)}\n")
    except Exception as e:
        print(f"写入日志时出错: {e}")
    
    # 返回待删除文件信息、分组信息和处理状态
    return files_to_delete_info, {"image_groups": image_groups, "video_groups": video_groups, "video_metadata": video_metadata}, processing_status

def generate_detailed_report(files_to_delete_by_dir, group_info_by_dir, log_file):
    """生成详细的重复文件报告"""
    report_file = os.path.splitext(log_file)[0] + "_详细报告.txt"
    
    try:
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write("=== 媒体文件重复组详细报告 ===\n")
            f.write(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            
            total_duplicate_groups = 0
            total_files_to_delete = sum(len(files) for files in files_to_delete_by_dir.values())
            f.write(f"总计发现 {total_files_to_delete} 个可删除的重复文件\n\n")
            
            for directory, group_info in group_info_by_dir.items():
                f.write(f"\n{'='*80}\n")
                f.write(f"目录: {directory}\n")
                f.write(f"{'='*80}\n")
                
                # 处理图片组
                image_groups = group_info["image_groups"]
                if image_groups:
                    f.write(f"\n--- 图片文件重复组 ({len(image_groups)}组) ---\n")
                    for i, (key, files) in enumerate(image_groups.items(), 1):
                        base_name, ext = key
                        f.write(f"\n图片组 {i}: {base_name}{ext} 系列\n")
                        
                        # 找出原始文件和副本
                        original_file = None
                        copies = []
                        for file in files:
                            if os.path.basename(file) == f"{base_name}{ext}":
                                original_file = file
                            else:
                                copies.append(file)
                        
                        if original_file:
                            size_mb = round(os.path.getsize(original_file) / (1024 * 1024), 2)
                            f.write(f"  [保留] {os.path.basename(original_file)} - {size_mb:.2f}MB\n")
                            
                        for copy in copies:
                            size_mb = round(os.path.getsize(copy) / (1024 * 1024), 2)
                            f.write(f"  [删除] {os.path.basename(copy)} - {size_mb:.2f}MB\n")
                
                # 处理视频组
                video_groups = group_info["video_groups"]
                video_metadata = group_info["video_metadata"]
                
                if video_groups:
                    f.write(f"\n--- 视频文件重复组 ({len(video_groups)}组) ---\n")
                    for i, (key, files) in enumerate(video_groups.items(), 1):
                        if len(files) <= 1:
                            continue
                            
                        size_mb, duration, fps = key
                        duration_str = f"{duration:.2f}s" if duration is not None else "未知"
                        fps_str = f"{fps:.2f}fps" if fps is not None else "未知"
                        
                        f.write(f"\n视频组 {i}: 大小 {size_mb}MB, 时长 {duration_str}, 帧率 {fps_str}\n")
                        
                        # 找出要保留的文件
                        file_to_keep = find_best_file_to_keep(files, video_metadata)
                        
                        # 输出要保留的文件信息
                        meta = video_metadata.get(file_to_keep, {})
                        f.write(f"  [保留] {os.path.basename(file_to_keep)}")
                        if 'size_mb' in meta:
                            f.write(f" - {meta['size_mb']:.2f}MB")
                        if 'duration' in meta and meta['duration'] is not None:
                            f.write(f", {meta['duration']:.2f}s")
                        if 'frame_rate' in meta and meta['frame_rate'] is not None:
                            f.write(f", {meta['frame_rate']:.2f}fps")
                        f.write("\n")
                        
                        # 输出要删除的文件
                        for file in files:
                            if file == file_to_keep:
                                continue
                                
                            meta = video_metadata.get(file, {})
                            f.write(f"  [删除] {os.path.basename(file)}")
                            if 'size_mb' in meta:
                                f.write(f" - {meta['size_mb']:.2f}MB")
                            if 'duration' in meta and meta['duration'] is not None:
                                f.write(f", {meta['duration']:.2f}s")
                            if 'frame_rate' in meta and meta['frame_rate'] is not None:
                                f.write(f", {meta['frame_rate']:.2f}fps")
                            f.write("\n")
                
                total_duplicate_groups += len(image_groups) + len(video_groups)
            
            f.write(f"\n\n总计发现 {total_duplicate_groups} 组重复文件，共 {total_files_to_delete} 个可删除文件")
            
    except Exception as e:
        print(f"生成详细报告时出错: {e}")
        return None
    
    return report_file

def main():
    print("=== 媒体重复文件清理工具 ===")
    print("请输入要处理的文件夹路径：")
    root_directory = input("> ").strip()
    
    if not os.path.isdir(root_directory):
        print(f"错误: 目录 '{root_directory}' 不存在")
        sys.exit(1)
    
    print(f"开始处理目录: {root_directory}")
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    log_file = os.path.join(os.getcwd(), f"delete_operation_{timestamp}.log")
    
    try:
        with open(log_file, 'w', encoding='utf-8') as f:
            f.write(f"开始时间: {datetime.now()}\n")
            f.write(f"根目录: {root_directory}\n\n")
    except Exception as e:
        print(f"无法创建日志文件: {e}")
        sys.exit(1)
    
    processed_dirs = 0
    
    # 第一阶段：扫描所有目录，收集要删除的文件和重复组信息
    files_to_delete_by_dir = {}
    group_info_by_dir = {}
    total_processing_status = {
        'image_processing': {
            'total_files': 0,
            'duplicate_groups': 0,
            'files_to_delete': 0
        },
        'video_processing': {
            'total_files': 0,
            'duplicate_groups': 0,
            'files_to_delete': 0
        }
    }
    
    for root, dirs, files in os.walk(root_directory):
        has_media = any(
            os.path.splitext(f)[1].lower() in {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', 
                                              '.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv', '.webm'}
            for f in files
        )
        
        if has_media:
            processed_dirs += 1
            print(f"\r扫描目录: {processed_dirs}", end='', flush=True)
            files_to_delete, group_info, processing_status = process_directory(root, log_file)
            
            # 更新总处理状态
            for key in ['image_processing', 'video_processing']:
                total_processing_status[key]['total_files'] += processing_status[key]['total_files']
                total_processing_status[key]['duplicate_groups'] += processing_status[key]['duplicate_groups']
                total_processing_status[key]['files_to_delete'] += processing_status[key]['files_to_delete']
            
            if files_to_delete:
                files_to_delete_by_dir[root] = files_to_delete
                group_info_by_dir[root] = group_info
    
    print("\n\n处理状态汇总：")
    print("=" * 50)
    print("图片处理：")
    print(f"  总文件数：{total_processing_status['image_processing']['total_files']}")
    print(f"  重复组数：{total_processing_status['image_processing']['duplicate_groups']}")
    print(f"  待删除文件数：{total_processing_status['image_processing']['files_to_delete']}")
    print("\n视频处理：")
    print(f"  总文件数：{total_processing_status['video_processing']['total_files']}")
    print(f"  重复组数：{total_processing_status['video_processing']['duplicate_groups']}")
    print(f"  待删除文件数：{total_processing_status['video_processing']['files_to_delete']}")
    print("=" * 50)
    
    # 汇总所有要删除的文件
    all_files_to_delete = []
    for files in files_to_delete_by_dir.values():
        all_files_to_delete.extend(files)
    
    # 第二阶段：生成详细报告
    if not all_files_to_delete:
        print("\n没有找到需要删除的重复文件")
        with open(log_file, 'a', encoding='utf-8') as f:
            f.write("\n结果: 未找到需要删除的重复文件\n")
        return
    
    print(f"\n找到 {len(all_files_to_delete)} 个需要删除的重复文件")
    
    # 生成详细报告
    report_file = generate_detailed_report(files_to_delete_by_dir, group_info_by_dir, log_file)
    if not report_file:
        print("无法生成详细报告文件，操作取消")
        return
    
    print(f"\n已生成详细的重复文件报告: {report_file}")
    
    # 尝试打开报告文件
    try:
        print("正在打开报告文件，请检查内容后关闭并返回此程序...")
        webbrowser.open(report_file)
    except:
        print(f"无法自动打开报告文件，请手动打开查看: {report_file}")
    
    # 终端中显示简要汇总信息
    print(f"\n{'='*60}")
    print(f"总计 {len(all_files_to_delete)} 个待删除文件")
    print(f"{'='*60}")
    print("\n请先查看详细报告文件，然后再决定是否进行删除操作。")
    
    # 等待用户确认
    confirmation = input("\n已查看报告文件，确定要删除所有标记的文件吗？(y/N): ").strip().lower()
    if confirmation != 'y':
        print("操作已取消")
        with open(log_file, 'a', encoding='utf-8') as f:
            f.write("\n结果: 用户取消操作\n")
        return
    
    # 执行删除操作
    print("\n开始删除文件...")
    deleted_count = 0
    failed_count = 0
    
    for i, file_info in enumerate(all_files_to_delete, 1):
        if i % 50 == 0:
            print(f"已处理 {i}/{len(all_files_to_delete)} 个文件...")
        
        file_path = file_info['path']
        
        if not os.path.exists(file_path):
            failed_count += 1
            with open(log_file, 'a', encoding='utf-8') as f:
                f.write(f"删除失败: {file_path}, 原因: 文件不存在\n")
            continue
        
        try:
            os.remove(file_path)
            deleted_count += 1
        except Exception as e:
            failed_count += 1
            with open(log_file, 'a', encoding='utf-8') as f:
                f.write(f"删除失败: {file_path}, 错误: {e}\n")
    
    # 更新日志和显示结果
    with open(log_file, 'a', encoding='utf-8') as f:
        f.write(f"\n\n删除结果:\n")
        f.write(f"成功删除: {deleted_count} 个文件\n")
        f.write(f"删除失败: {failed_count} 个文件\n")
        f.write(f"结束时间: {datetime.now()}\n")
    
    print(f"\n操作完成")
    print(f"成功删除: {deleted_count} 个文件")
    print(f"删除失败: {failed_count} 个文件")
    print(f"详细日志已保存到: {log_file}")

if __name__ == "__main__":
    main() 