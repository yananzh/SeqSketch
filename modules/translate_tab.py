from .base_tab import BaseTabWidget
import re
from PyQt6.QtWidgets import QMessageBox, QComboBox

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
AA_3LETTER = {
    'A': 'Ala', 'R': 'Arg', 'N': 'Asn', 'D': 'Asp', 'C': 'Cys',
    'Q': 'Gln', 'E': 'Glu', 'G': 'Gly', 'H': 'His', 'I': 'Ile',
    'L': 'Leu', 'K': 'Lys', 'M': 'Met', 'F': 'Phe', 'P': 'Pro',
    'S': 'Ser', 'T': 'Thr', 'W': 'Trp', 'Y': 'Tyr', 'V': 'Val', '*': 'Stop'
}

class TranslateTab(BaseTabWidget):
    def __init__(self, parent=None):
        super().__init__("翻译序列", parent)
        self.frame_box = QComboBox()
        self.frame_box.addItems([
            "+1 (正链, 从第1位)", "+2 (正链, 从第2位)", "+3 (正链, 从第3位)",
            "-1 (反链, 从第1位)", "-2 (反链, 从第2位)", "-3 (反链, 从第3位)"
        ])
        self.aa_mode_box = QComboBox()
        self.aa_mode_box.addItems(["单字母缩写", "三字母缩写"])
        self.layout().insertWidget(1, self.frame_box)
        self.layout().insertWidget(2, self.aa_mode_box)

    def run(self):
        seq = self.input_text.toPlainText().strip().replace("\n", "").replace(" ", "")
        if not seq:
            self.status_label.setText("请输入DNA或RNA序列！")
            return
        seq = seq.upper().replace('U', 'T')  # RNA转DNA
        if not re.fullmatch(r'[ACGTN]+', seq):
            self.status_label.setText("输入序列包含无效字符，仅允许A/T/G/C/N！")
            return
        frame = self.frame_box.currentIndex()
        aa_mode = self.aa_mode_box.currentIndex()
        if frame < 3:
            offset = frame
            trans_seq = self.translate(seq[offset:], aa_mode)
        else:
            offset = frame - 3
            revcomp = self.reverse_complement(seq)
            trans_seq = self.translate(revcomp[offset:], aa_mode)
        self.output_text.setPlainText(trans_seq)
        self.status_label.setText("已翻译序列")

    def translate(self, seq, aa_mode):
        aa_seq = []
        for i in range(0, len(seq)-2, 3):
            codon = seq[i:i+3]
            if len(codon) < 3:
                break
            aa = CODON_TABLE.get(codon, 'X')
            if aa_mode == 0:
                aa_seq.append(aa)
            else:
                aa_seq.append(AA_3LETTER.get(aa, 'Xxx'))
        return '-'.join(aa_seq) if aa_mode == 1 else ''.join(aa_seq)

    def reverse_complement(self, seq):
        comp_map = str.maketrans('ACGT', 'TGCA')
        return seq.translate(comp_map)[::-1]

    def show_help(self):
        QMessageBox.information(self, "翻译序列 帮助", "支持DNA/RNA到蛋白质的翻译，6种读框，标准密码子表，支持单/三字母氨基酸缩写。*") 