from utils.common_components import BaseTabWidget
import re
from PyQt6.QtWidgets import QMessageBox, QSpinBox, QComboBox

CODON_TABLE = {
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
    'GGT': 'G', 'GGC': 'G', 'GGA': 'G', 'GGG': 'G',
}

class ORFTab(BaseTabWidget):
    def __init__(self, parent=None):
        super().__init__("ORF Finder", "sequence")
        self.min_len_box = QSpinBox()
        self.min_len_box.setRange(30, 10000)
        self.min_len_box.setValue(100)
        self.chain_box = QComboBox()
        self.chain_box.addItems(["正链", "反链", "正+反链"])
        self.add_content_widget(self.min_len_box)
        self.add_content_widget(self.chain_box)

    def run(self):
        seq = self.input_text.toPlainText().strip().replace("\n", "").replace(" ", "")
        if not seq:
            self.status_label.setText("请输入DNA序列！")
            return
        seq = seq.upper().replace('U', 'T')
        if not re.fullmatch(r'[ACGTN]+', seq):
            self.status_label.setText("输入序列包含无效字符，仅允许A/T/G/C/N！")
            return
        min_len = self.min_len_box.value()
        chain_mode = self.chain_box.currentIndex()
        results = []
        if chain_mode in (0, 2):
            results += self.find_orfs(seq, '+')
        if chain_mode in (1, 2):
            revcomp = self.reverse_complement(seq)
            results += self.find_orfs(revcomp, '-')
        results = [orf for orf in results if orf['length'] >= min_len]
        if not results:
            self.output_text.setPlainText("未找到满足条件的ORF。")
            self.status_label.setText("无ORF")
            return
        out = []
        for orf in results:
            out.append(f"读框: {orf['frame']} | 位置: {orf['start']+1}-{orf['end']} | 长度: {orf['length']} nt\n序列: {orf['seq']}\n翻译: {orf['aa']}\n")
        self.output_text.setPlainText('\n'.join(out))
        self.status_label.setText(f"共找到{len(results)}个ORF")

    def find_orfs(self, seq, strand):
        orfs = []
        for frame in range(3):
            i = frame
            while i < len(seq)-2:
                codon = seq[i:i+3]
                if codon == 'ATG':
                    for j in range(i+3, len(seq)-2, 3):
                        stop = seq[j:j+3]
                        if stop in ('TAA', 'TAG', 'TGA'):
                            orf_seq = seq[i:j+3]
                            aa = self.translate(orf_seq)
                            orfs.append({
                                'frame': f"{strand}{frame+1}",
                                'start': i if strand=="+" else len(seq)-j-2,
                                'end': j+3 if strand=="+" else len(seq)-i,
                                'length': len(orf_seq),
                                'seq': orf_seq,
                                'aa': aa
                            })
                            i = j+3
                            break
                    else:
                        i += 3
                else:
                    i += 3
        return orfs

    def translate(self, seq):
        aa_seq = []
        for i in range(0, len(seq)-2, 3):
            codon = seq[i:i+3]
            aa = CODON_TABLE.get(codon, 'X')
            aa_seq.append(aa)
        return ''.join(aa_seq)

    def reverse_complement(self, seq):
        comp_map = str.maketrans('ACGT', 'TGCA')
        return seq.translate(comp_map)[::-1]

    def show_help(self):
        QMessageBox.information(self, "ORF Finder 帮助", "查找所有可能的开放阅读框，支持最小ORF长度阈值，显示ORF的位置、长度、读框和翻译结果，支持正向和反向链。") 