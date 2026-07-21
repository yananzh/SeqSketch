"""
序列分析模块

提供序列分析、比对、统计等功能
支持DNA和蛋白质序列分析
"""

import math
import re
from collections import Counter
from typing import Dict, List, Optional, Tuple

try:
    from .fasta_processor import FASTARecord
except ImportError:
    from fasta_processor import FASTARecord


class SequenceAnalyzer:
    """序列分析器"""

    def __init__(self):
        # DNA密码子表
        self.codon_table = {
            'TTT': 'F', 'TTC': 'F', 'TTA': 'L', 'TTG': 'L',
            'TCT': 'S', 'TCC': 'S', 'TCA': 'S', 'TCG': 'S',
            'TAT': 'Y', 'TAC': 'Y', 'TAA': '*', 'TAG': '*',
            'TGT': 'C', 'TGC': 'C', 'TGA': '*', 'TGG': 'W',
            'CTT': 'L', 'CTC': 'L', 'CTA': 'L', 'CTG': 'L',
            'CCT': 'P', 'CCC': 'P', 'CCA': 'P', 'CCG': 'P',
            'CAT': 'H', 'CAC': 'H', 'CAA': 'Q', 'CAG': 'Q',
            'CGT': 'R', 'CGC': 'R', 'CGA': 'R', 'CGG': 'R',
            'ATT': 'I', 'ATC': 'I', 'ATA': 'I', 'ATG': 'M',
            'ACT': 'T', 'ACC': 'T', 'ACA': 'T', 'ACG': 'T',
            'AAT': 'N', 'AAC': 'N', 'AAA': 'K', 'AAG': 'K',
            'AGT': 'S', 'AGC': 'S', 'AGA': 'R', 'AGG': 'R',
            'GTT': 'V', 'GTC': 'V', 'GTA': 'V', 'GTG': 'V',
            'GCT': 'A', 'GCC': 'A', 'GCA': 'A', 'GCG': 'A',
            'GAT': 'D', 'GAC': 'D', 'GAA': 'E', 'GAG': 'E',
            'GGT': 'G', 'GGC': 'G', 'GGA': 'G', 'GGG': 'G'
        }

        # 氨基酸性质
        self.amino_acid_properties = {
            'A': {'name': 'Alanine', 'hydrophobicity': 1.8, 'polarity': 0.0},
            'R': {'name': 'Arginine', 'hydrophobicity': -4.5, 'polarity': 3.0},
            'N': {'name': 'Asparagine', 'hydrophobicity': -3.5, 'polarity': 2.0},
            'D': {'name': 'Aspartic acid', 'hydrophobicity': -3.5, 'polarity': 3.0},
            'C': {'name': 'Cysteine', 'hydrophobicity': 2.5, 'polarity': 1.0},
            'Q': {'name': 'Glutamine', 'hydrophobicity': -3.5, 'polarity': 2.0},
            'E': {'name': 'Glutamic acid', 'hydrophobicity': -3.5, 'polarity': 3.0},
            'G': {'name': 'Glycine', 'hydrophobicity': -0.4, 'polarity': 0.0},
            'H': {'name': 'Histidine', 'hydrophobicity': -3.2, 'polarity': 2.0},
            'I': {'name': 'Isoleucine', 'hydrophobicity': 4.5, 'polarity': 0.0},
            'L': {'name': 'Leucine', 'hydrophobicity': 3.8, 'polarity': 0.0},
            'K': {'name': 'Lysine', 'hydrophobicity': -3.9, 'polarity': 3.0},
            'M': {'name': 'Methionine', 'hydrophobicity': 1.9, 'polarity': 0.0},
            'F': {'name': 'Phenylalanine', 'hydrophobicity': 2.8, 'polarity': 0.0},
            'P': {'name': 'Proline', 'hydrophobicity': -1.6, 'polarity': 0.0},
            'S': {'name': 'Serine', 'hydrophobicity': -0.8, 'polarity': 1.0},
            'T': {'name': 'Threonine', 'hydrophobicity': -0.7, 'polarity': 1.0},
            'W': {'name': 'Tryptophan', 'hydrophobicity': -0.9, 'polarity': 0.0},
            'Y': {'name': 'Tyrosine', 'hydrophobicity': -1.3, 'polarity': 1.0},
            'V': {'name': 'Valine', 'hydrophobicity': 4.2, 'polarity': 0.0}
        }

    def analyze_dna_sequence(self, sequence: str) -> Dict:
        """
        分析DNA序列
        
        Args:
            sequence: DNA序列
            
        Returns:
            Dict: 分析结果
        """
        sequence = sequence.upper()

        # 基本统计
        length = len(sequence)
        base_counts = Counter(sequence)

        # GC含量
        gc_count = base_counts.get('G', 0) + base_counts.get('C', 0)
        gc_content = (gc_count / length * 100) if length > 0 else 0

        # 碱基组成
        base_composition = {base: base_counts.get(base, 0) for base in 'ATGC'}

        # 重复序列分析
        repeats = self._find_repeats(sequence)

        # 限制性酶切位点
        restriction_sites = self._find_restriction_sites(sequence)

        return {
            'length': length,
            'gc_content': round(gc_content, 2),
            'base_composition': base_composition,
            'repeats': repeats,
            'restriction_sites': restriction_sites
        }

    def translate_dna(self, sequence: str, frame: int = 1) -> str:
        """
        翻译DNA序列为蛋白质序列
        
        Args:
            sequence: DNA序列
            frame: 阅读框 (1, 2, 3, -1, -2, -3)
            
        Returns:
            str: 蛋白质序列
        """
        sequence = sequence.upper()

        # 处理不同的阅读框
        if frame < 0:
            # 反向互补
            complement = {'A': 'T', 'T': 'A', 'G': 'C', 'C': 'G', 'N': 'N'}
            sequence = ''.join(complement.get(base, base) for base in reversed(sequence))
            frame = abs(frame)

        # 调整起始位置
        start_pos = frame - 1
        coding_sequence = sequence[start_pos:]

        # 确保长度是3的倍数
        if len(coding_sequence) % 3 != 0:
            coding_sequence = coding_sequence[:-(len(coding_sequence) % 3)]

        # 翻译
        protein = ""
        for i in range(0, len(coding_sequence), 3):
            codon = coding_sequence[i:i+3]
            if len(codon) == 3:
                amino_acid = self.codon_table.get(codon, 'X')
                protein += amino_acid

        return protein

    def analyze_protein_sequence(self, sequence: str) -> Dict:
        """
        分析蛋白质序列
        
        Args:
            sequence: 蛋白质序列
            
        Returns:
            Dict: 分析结果
        """
        sequence = sequence.upper()
        length = len(sequence)

        # 氨基酸组成
        aa_counts = Counter(sequence)
        aa_composition = {aa: aa_counts.get(aa, 0) for aa in self.amino_acid_properties.keys()}

        # 分子量计算（简化版）
        molecular_weight = self._calculate_molecular_weight(sequence)

        # 等电点估算（简化版）
        isoelectric_point = self._estimate_isoelectric_point(sequence)

        # 疏水性分析
        hydrophobicity = self._calculate_hydrophobicity(sequence)

        # 二级结构预测（简化版）
        secondary_structure = self._predict_secondary_structure(sequence)

        return {
            'length': length,
            'amino_acid_composition': aa_composition,
            'molecular_weight': round(molecular_weight, 2),
            'isoelectric_point': round(isoelectric_point, 2),
            'hydrophobicity': round(hydrophobicity, 2),
            'secondary_structure': secondary_structure
        }

    def calculate_similarity(self, seq1: str, seq2: str) -> Dict:
        """
        计算两个序列的相似性
        
        Args:
            seq1: 序列1
            seq2: 序列2
            
        Returns:
            Dict: 相似性分析结果
        """
        seq1, seq2 = seq1.upper(), seq2.upper()

        # 确保长度相同
        min_length = min(len(seq1), len(seq2))
        seq1 = seq1[:min_length]
        seq2 = seq2[:min_length]

        # 计算匹配
        matches = sum(1 for a, b in zip(seq1, seq2) if a == b)
        similarity = (matches / min_length * 100) if min_length > 0 else 0

        # 计算差异
        differences = min_length - matches

        # 计算编辑距离（简化版）
        edit_distance = self._calculate_edit_distance(seq1, seq2)

        return {
            'similarity_percentage': round(similarity, 2),
            'matches': matches,
            'differences': differences,
            'edit_distance': edit_distance,
            'aligned_length': min_length
        }

    def find_motifs(self, sequence: str, motif_pattern: str) -> List[Dict]:
        """
        在序列中查找基序
        
        Args:
            sequence: 序列
            motif_pattern: 基序模式（支持正则表达式）
            
        Returns:
            List[Dict]: 找到的基序列表
        """
        sequence = sequence.upper()
        motifs = []

        try:
            pattern = re.compile(motif_pattern, re.IGNORECASE)
            for match in pattern.finditer(sequence):
                motifs.append({
                    'start': match.start(),
                    'end': match.end(),
                    'sequence': match.group(),
                    'length': len(match.group())
                })
        except re.error:
            # 如果不是有效的正则表达式，进行简单的字符串搜索
            motif_pattern = motif_pattern.upper()
            start = 0
            while True:
                pos = sequence.find(motif_pattern, start)
                if pos == -1:
                    break
                motifs.append({
                    'start': pos,
                    'end': pos + len(motif_pattern),
                    'sequence': motif_pattern,
                    'length': len(motif_pattern)
                })
                start = pos + 1

        return motifs

    def _find_repeats(self, sequence: str, min_length: int = 3, max_length: int = 20) -> List[Dict]:
        """查找重复序列"""
        repeats = []

        for length in range(min_length, min(max_length + 1, len(sequence) // 2 + 1)):
            for i in range(len(sequence) - length + 1):
                pattern = sequence[i:i+length]
                count = sequence.count(pattern)
                if count > 1:
                    # 检查是否已经记录过
                    exists = any(r['pattern'] == pattern for r in repeats)
                    if not exists:
                        repeats.append({
                            'pattern': pattern,
                            'length': length,
                            'count': count,
                            'positions': [pos for pos in range(len(sequence) - length + 1)
                                         if sequence[pos:pos+length] == pattern]
                        })

        # 按长度排序
        repeats.sort(key=lambda x: x['length'], reverse=True)
        return repeats[:10]  # 返回前10个最长的重复

    def _find_restriction_sites(self, sequence: str) -> Dict[str, List[int]]:
        """查找限制性酶切位点"""
        # 常见的限制性酶切位点
        restriction_enzymes = {
            'EcoRI': 'GAATTC',
            'BamHI': 'GGATCC',
            'HindIII': 'AAGCTT',
            'PstI': 'CTGCAG',
            'XbaI': 'TCTAGA',
            'SalI': 'GTCGAC',
            'KpnI': 'GGTACC',
            'SmaI': 'CCCGGG'
        }

        sites = {}
        for enzyme, site in restriction_enzymes.items():
            positions = []
            start = 0
            while True:
                pos = sequence.find(site, start)
                if pos == -1:
                    break
                positions.append(pos)
                start = pos + 1
            if positions:
                sites[enzyme] = positions

        return sites

    def _calculate_molecular_weight(self, protein: str) -> float:
        """计算蛋白质分子量（简化版）"""
        # 氨基酸分子量（Da）
        aa_weights = {
            'A': 89.1, 'R': 174.2, 'N': 132.1, 'D': 133.1, 'C': 121.2,
            'Q': 146.2, 'E': 147.1, 'G': 75.1, 'H': 155.2, 'I': 131.2,
            'L': 131.2, 'K': 146.2, 'M': 149.2, 'F': 165.2, 'P': 115.1,
            'S': 105.1, 'T': 119.1, 'W': 204.2, 'Y': 181.2, 'V': 117.1
        }

        weight = sum(aa_weights.get(aa, 110.0) for aa in protein)
        # 减去水分子的重量（每个肽键形成时失去一个水分子）
        weight -= (len(protein) - 1) * 18.0
        return weight

    def _estimate_isoelectric_point(self, protein: str) -> float:
        """估算等电点（简化版）"""
        # 酸性氨基酸
        acidic = protein.count('D') + protein.count('E')
        # 碱性氨基酸
        basic = protein.count('R') + protein.count('K') + protein.count('H')

        # 简化的等电点计算
        if acidic > basic:
            return 4.0
        elif basic > acidic:
            return 9.0
        else:
            return 6.5

    def _calculate_hydrophobicity(self, protein: str) -> float:
        """计算平均疏水性"""
        if not protein:
            return 0.0

        total_hydrophobicity = sum(
            self.amino_acid_properties.get(aa, {}).get('hydrophobicity', 0)
            for aa in protein
        )
        return total_hydrophobicity / len(protein)

    def _predict_secondary_structure(self, protein: str) -> Dict[str, float]:
        """预测二级结构（简化版）"""
        # 简化的二级结构预测规则
        alpha_helix = 0
        beta_sheet = 0

        for i in range(len(protein) - 3):
            window = protein[i:i+4]
            # 简单的α螺旋倾向性
            if any(aa in window for aa in 'AEKQR'):
                alpha_helix += 1
            # 简单的β折叠倾向性
            if any(aa in window for aa in 'VILFYW'):
                beta_sheet += 1

        total_windows = max(1, len(protein) - 3)

        return {
            'alpha_helix': round(alpha_helix / total_windows * 100, 1),
            'beta_sheet': round(beta_sheet / total_windows * 100, 1),
            'random_coil': round(100 - (alpha_helix + beta_sheet) / total_windows * 100, 1)
        }

    def _calculate_edit_distance(self, seq1: str, seq2: str) -> int:
        """计算编辑距离（Levenshtein距离）"""
        m, n = len(seq1), len(seq2)
        dp = [[0] * (n + 1) for _ in range(m + 1)]

        for i in range(m + 1):
            dp[i][0] = i
        for j in range(n + 1):
            dp[0][j] = j

        for i in range(1, m + 1):
            for j in range(1, n + 1):
                if seq1[i-1] == seq2[j-1]:
                    dp[i][j] = dp[i-1][j-1]
                else:
                    dp[i][j] = min(dp[i-1][j], dp[i][j-1], dp[i-1][j-1]) + 1

        return dp[m][n]
