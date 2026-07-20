"""
FASTA文件处理模块

提供FASTA文件的读取、解析、验证、统计等功能
支持单文件和多文件处理
"""

import os
import re
from typing import Dict, List, Tuple, Optional, Generator
from dataclasses import dataclass
from pathlib import Path
import logging

# 配置日志
logger = logging.getLogger(__name__)


@dataclass
class FASTARecord:
    """FASTA记录数据结构"""
    header: str
    sequence: str
    description: str = ""
    
    def __post_init__(self):
        """初始化后处理"""
        self.sequence = self.sequence.upper()
        self.length = len(self.sequence)
    
    def get_gc_content(self) -> float:
        """计算GC含量"""
        if self.length == 0:
            return 0.0
        gc_count = self.sequence.count('G') + self.sequence.count('C')
        return (gc_count / self.length) * 100
    
    def get_base_composition(self) -> Dict[str, int]:
        """获取碱基组成"""
        composition = {}
        for base in 'ATGC':
            composition[base] = self.sequence.count(base)
        return composition


class FASTAProcessor:
    """FASTA文件处理器"""
    
    def __init__(self):
        self.records: List[FASTARecord] = []
        self.file_path: Optional[str] = None
    
    def read_file(self, file_path: str) -> bool:
        """
        读取FASTA文件
        
        Args:
            file_path: FASTA文件路径
            
        Returns:
            bool: 是否成功读取
        """
        try:
            self.file_path = file_path
            self.records = []
            try:
                f = open(file_path, 'r', encoding='utf-8')
            except Exception:
                f = open(file_path, 'r', encoding='latin-1')
            with f as fobj:
                current_header = ""
                current_sequence = ""
                for line_num, line in enumerate(fobj, 1):
                    line = line.strip()
                    if line.startswith('>'):
                        if current_header and current_sequence:
                            self._add_record(current_header, current_sequence)
                        current_header = line[1:]
                        current_sequence = ""
                    else:
                        if current_header:
                            current_sequence += line
                if current_header and current_sequence:
                    self._add_record(current_header, current_sequence)
            logger.info(f"Successfully read FASTA file: {file_path}, {len(self.records)} records")
            return True
        except Exception as e:
            logger.error(f"Failed to read FASTA file: {e}")
            return False
    
    def _add_record(self, header: str, sequence: str):
        """添加FASTA记录"""
        # 分离描述信息
        parts = header.split(' ', 1)
        id_part = parts[0]
        description = parts[1] if len(parts) > 1 else ""
        
        # 清理序列（移除空白字符）
        clean_sequence = re.sub(r'\s+', '', sequence)
        
        record = FASTARecord(
            header=id_part,
            sequence=clean_sequence,
            description=description
        )
        self.records.append(record)
    
    def validate_file(self) -> Tuple[bool, List[str]]:
        """
        验证FASTA文件格式
        
        Returns:
            Tuple[bool, List[str]]: (是否有效, 错误信息列表)
        """
        errors = []

        if not self.records:
            errors.append("File is empty or has invalid format")
            return False, errors

        for i, record in enumerate(self.records):
            if record.length == 0:
                errors.append(f"Record {i+1} ({record.header}): sequence is empty")

            invalid_chars = set(record.sequence) - set('ATGCUNRYMKSWBDHVatgcunrymkswbdhv')
            if invalid_chars:
                errors.append(f"Record {i+1} ({record.header}): contains invalid characters {invalid_chars}")
        
        return len(errors) == 0, errors
    
    def get_statistics(self) -> Dict:
        """
        获取文件统计信息
        
        Returns:
            Dict: 统计信息字典
        """
        if not self.records:
            return {}
        
        total_sequences = len(self.records)
        total_length = sum(record.length for record in self.records)
        avg_length = total_length / total_sequences
        
        # 长度统计
        lengths = [record.length for record in self.records]
        min_length = min(lengths)
        max_length = max(lengths)
        
        # GC含量统计
        gc_contents = [record.get_gc_content() for record in self.records]
        avg_gc = sum(gc_contents) / len(gc_contents)
        
        # 碱基组成统计
        total_composition = {'A': 0, 'T': 0, 'G': 0, 'C': 0}
        for record in self.records:
            comp = record.get_base_composition()
            for base, count in comp.items():
                total_composition[base] += count
        
        return {
            'total_sequences': total_sequences,
            'total_length': total_length,
            'average_length': round(avg_length, 2),
            'min_length': min_length,
            'max_length': max_length,
            'average_gc_content': round(avg_gc, 2),
            'base_composition': total_composition,
            'file_path': self.file_path
        }
    
    def filter_sequences(self, min_length: int = 0, max_length: int = None, 
                        min_gc: float = 0, max_gc: float = 100) -> List[FASTARecord]:
        """
        根据条件过滤序列
        
        Args:
            min_length: 最小长度
            max_length: 最大长度
            min_gc: 最小GC含量
            max_gc: 最大GC含量
            
        Returns:
            List[FASTARecord]: 过滤后的序列列表
        """
        filtered = []
        
        for record in self.records:
            # 长度过滤
            if record.length < min_length:
                continue
            if max_length and record.length > max_length:
                continue
            
            # GC含量过滤
            gc_content = record.get_gc_content()
            if gc_content < min_gc or gc_content > max_gc:
                continue
            
            filtered.append(record)
        
        return filtered
    
    def save_file(self, output_path: str, records: List[FASTARecord] = None) -> bool:
        """
        保存FASTA文件
        
        Args:
            output_path: 输出文件路径
            records: 要保存的记录列表，默认为所有记录
            
        Returns:
            bool: 是否成功保存
        """
        try:
            if records is None:
                records = self.records
            
            with open(output_path, 'w', encoding='utf-8') as f:
                for record in records:
                    # 写入头部
                    if record.description:
                        f.write(f">{record.header} {record.description}\n")
                    else:
                        f.write(f">{record.header}\n")
                    
                    # 写入序列（每行80个字符）
                    sequence = record.sequence
                    for i in range(0, len(sequence), 80):
                        f.write(sequence[i:i+80] + "\n")
            
            logger.info(f"Successfully saved FASTA file: {output_path}")
            return True

        except Exception as e:
            logger.error(f"Failed to save FASTA file: {e}")
            return False
    
    def get_sequence_by_id(self, sequence_id: str) -> Optional[FASTARecord]:
        """
        根据ID获取序列
        
        Args:
            sequence_id: 序列ID
            
        Returns:
            Optional[FASTARecord]: 找到的序列记录
        """
        for record in self.records:
            if record.header == sequence_id:
                return record
        return None
    
    def search_sequences(self, pattern: str, case_sensitive: bool = False) -> List[FASTARecord]:
        """
        搜索序列（在头部和描述中搜索）
        
        Args:
            pattern: 搜索模式
            case_sensitive: 是否区分大小写
            
        Returns:
            List[FASTARecord]: 匹配的序列列表
        """
        matches = []
        flags = 0 if case_sensitive else re.IGNORECASE
        
        for record in self.records:
            search_text = f"{record.header} {record.description}"
            if re.search(pattern, search_text, flags):
                matches.append(record)
        
        return matches
    
    def reverse_complement(self, sequence: str) -> str:
        """
        获取序列的反向互补序列
        
        Args:
            sequence: 原始序列
            
        Returns:
            str: 反向互补序列
        """
        complement = {'A': 'T', 'T': 'A', 'G': 'C', 'C': 'G', 'N': 'N'}
        return ''.join(complement.get(base, base) for base in reversed(sequence))
    
    def create_reverse_complement_records(self) -> List[FASTARecord]:
        """
        为所有序列创建反向互补记录
        
        Returns:
            List[FASTARecord]: 反向互补序列记录列表
        """
        rc_records = []
        
        for record in self.records:
            rc_sequence = self.reverse_complement(record.sequence)
            rc_record = FASTARecord(
                header=f"{record.header}_reverse_complement",
                sequence=rc_sequence,
                description=f"Reverse complement of {record.header}"
            )
            rc_records.append(rc_record)
        
        return rc_records


def batch_process_fasta_files(file_paths: List[str], 
                             output_dir: str = "output") -> Dict[str, Dict]:
    """
    批量处理FASTA文件
    
    Args:
        file_paths: FASTA文件路径列表
        output_dir: 输出目录
        
    Returns:
        Dict[str, Dict]: 处理结果字典
    """
    results = {}
    
    # 创建输出目录
    Path(output_dir).mkdir(exist_ok=True)
    
    for file_path in file_paths:
        try:
            processor = FASTAProcessor()
            if processor.read_file(file_path):
                # 获取统计信息
                stats = processor.get_statistics()
                
                # 验证文件
                is_valid, errors = processor.validate_file()
                
                # 保存处理结果
                filename = Path(file_path).stem
                output_file = Path(output_dir) / f"{filename}_processed.fasta"
                
                if processor.save_file(str(output_file)):
                    results[file_path] = {
                        'status': 'success',
                        'statistics': stats,
                        'is_valid': is_valid,
                        'errors': errors,
                        'output_file': str(output_file)
                    }
                else:
                    results[file_path] = {
                        'status': 'error',
                        'message': 'Failed to save file'
                    }
            else:
                results[file_path] = {
                    'status': 'error',
                    'message': 'Failed to read file'
                }
                
        except Exception as e:
            results[file_path] = {
                'status': 'error',
                'message': str(e)
            }
    
    return results