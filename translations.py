"""
Translation system for BioSeq Analyzer
Provides simple dictionary-based translations for Chinese and English
"""

# Translation dictionaries
TRANSLATIONS = {
    'zh_CN': {
        # Window titles
        'BioSeq Analyzer 生物序列分析器': 'BioSeq Analyzer 生物序列分析器',
        '错误': '错误',
        
        # Menu items
        'FASTA工具': 'FASTA工具',
        '序列长度统计': '序列长度统计',
        'ID 简化': 'ID 简化',
        '序列提取 (按ID)': '序列提取 (按ID)',
        '序列提取 (正则表达式)': '序列提取 (正则表达式)',
        '从NCBI下载序列': '从NCBI下载序列',
        '批量重命名ID': '批量重命名ID',
        
        'DNA序列分析': 'DNA序列分析',
        '转成RNA': '转成RNA',
        '互补序列': '互补序列',
        '反向互补序列': '反向互补序列',
        '翻译序列': '翻译序列',
        'ORF Finder': 'ORF Finder',
        '桑格测序数据处理': '桑格测序数据处理',
        
        '蛋白质序列分析': '蛋白质序列分析',
        '氨基酸组成': '氨基酸组成',
        '物化性质计算': '物化性质计算',
        '二级结构预测': '二级结构预测',
        '三级结构预测': '三级结构预测',
        '结构域预测': '结构域预测',
        '信号肽预测': '信号肽预测',
        '跨膜螺旋预测': '跨膜螺旋预测',
        '同源蛋白搜索': '同源蛋白搜索',
        '结构相似蛋白搜索': '结构相似蛋白搜索',
        
        '序列比对': '序列比对',
        '双序列比对 (在线工具)': '双序列比对 (在线工具)',
        '多序列比对 (在线工具)': '多序列比对 (在线工具)',
        '序列标识图 (在线工具)': '序列标识图 (在线工具)',
        
        'BLAST分析': 'BLAST分析',
        'NCBI在线BLAST': 'NCBI在线BLAST',
        '本地BLAST': '本地BLAST',
        '1. 构建BLAST数据库...': '1. 构建BLAST数据库...',
        '2. 运行BLAST查询...': '2. 运行BLAST查询...',
        
        '引物设计': '引物设计',
        'PCR 引物设计助手': 'PCR 引物设计助手',
        
        '进化树构建与可视化': '进化树构建与可视化',
        '系统发育树构建(在线工具)': '系统发育树构建(在线工具)',
        '进化树可视化（在线工具）': '进化树可视化（在线工具）',
        
        '收藏夹': '收藏夹',
        '管理收藏夹': '管理收藏夹',
        
        '设置': '设置',
        '外观主题': '外观主题',
        '浅色主题': '浅色主题',
        '深色主题': '深色主题',
        '界面语言': '界面语言',
        '检查更新': '检查更新',
        '关于': '关于',
        
        # Dialog texts
        '当前版本: v1.0.0\n\n暂无可用更新。\n\n您可以访问项目主页获取最新信息：\nhttps://github.com/yananzh/BioSeq-Analyzer': 
            '当前版本: v1.0.0\n\n暂无可用更新。\n\n您可以访问项目主页获取最新信息：\nhttps://github.com/yananzh/BioSeq-Analyzer',
        '关于 BioSeq Analyzer': '关于 BioSeq Analyzer',
        
        # Common UI elements
        '输入FASTA文件:': '输入FASTA文件:',
        '选择文件': '选择文件',
        '输出统计文件:': '输出统计文件:',
        '输出文件:': '输出文件:',
        '选择位置': '选择位置',
        '开始统计': '开始统计',
        '开始简化': '开始简化',
        '开始提取': '开始提取',
        '开始下载': '开始下载',
        '清空': '清空',
        '帮助': '帮助',
        '确定': '确定',
        '就绪': '就绪',
        '状态:': '状态:',
        '操作日志将显示在此处...': '操作日志将显示在此处...',
        '已清空': '已清空',
        
        # Help dialog titles
        '帮助 - 序列长度统计分析': '帮助 - 序列长度统计分析',
        '帮助 - 序列ID简化': '帮助 - 序列ID简化',
        '帮助 - 按ID提取序列': '帮助 - 按ID提取序列',
        '帮助 - 正则表达式提取序列': '帮助 - 正则表达式提取序列',
        '帮助 - NCBI序列下载': '帮助 - NCBI序列下载',
        '帮助 - 批量重命名序列ID': '帮助 - 批量重命名序列ID',
        
        # Additional UI elements
        '要提取的序列ID列表（每行一个）:': '要提取的序列ID列表（每行一个）:',
        '输入序列ID，每行一个\n例如:\nseq1\nseq2\nseq3': '输入序列ID，每行一个\n例如:\nseq1\nseq2\nseq3',
        '正则表达式:': '正则表达式:',
        '例如: gene.*protein, ^chr[0-9]+, .*hypothetical.*': '例如: gene.*protein, ^chr[0-9]+, .*hypothetical.*',
        'ID映射文件:': 'ID映射文件:',
        '选择映射文件': '选择映射文件',
        '映射文件包含标题行': '映射文件包含标题行',
        '开始重命名': '开始重命名',
        '选择FASTA文件': '选择FASTA文件',
        'FASTA文件 (*.fasta *.fa *.fas);;所有文件 (*)': 'FASTA文件 (*.fasta *.fa *.fas);;所有文件 (*)',
        '保存简化后的文件': '保存简化后的文件',
        
        # DNA processing help dialogs
        '转成RNA 帮助': '转成RNA 帮助',
        '将DNA序列中的T（胸腺嘧啶）替换为U（尿嘧啶），支持IUPAC代码和大小写输入。': '将DNA序列中的T（胸腺嘧啶）替换为U（尿嘧啶），支持IUPAC代码和大小写输入。',
        '互补序列 帮助': '互补序列 帮助',
        '生成DNA的互补序列：A↔T，G↔C，支持IUPAC代码和大小写输入，N保持不变。': '生成DNA的互补序列：A↔T，G↔C，支持IUPAC代码和大小写输入，N保持不变。',
        '反向互补序列 帮助': '反向互补序列 帮助',
        '先生成互补序列，再反向排列。常用于分子生物学操作和引物设计。支持IUPAC代码和大小写输入。': '先生成互补序列，再反向排列。常用于分子生物学操作和引物设计。支持IUPAC代码和大小写输入。',
        '翻译序列 帮助': '翻译序列 帮助',
        '支持DNA/RNA到蛋白质的翻译，6种读框，标准密码子表，支持单/三字母氨基酸缩写。': '支持DNA/RNA到蛋白质的翻译，6种读框，标准密码子表，支持单/三字母氨基酸缩写。',
        'ORF Finder 帮助': 'ORF Finder 帮助',
        '查找所有可能的开放阅读框，支持最小ORF长度阈值，显示ORF的位置、长度、读框和翻译结果，支持正向和反向链。': '查找所有可能的开放阅读框，支持最小ORF长度阈值，显示ORF的位置、长度、读框和翻译结果，支持正向和反向链。',
        '桑格测序数据处理': '桑格测序数据处理',
        
        # DNA processing status messages
        '请输入DNA序列！': '请输入DNA序列！',
        '请输入DNA或RNA序列！': '请输入DNA或RNA序列！',
        '输入序列包含无效字符，仅允许A/T/G/C/N等IUPAC代码！': '输入序列包含无效字符，仅允许A/T/G/C/N等IUPAC代码！',
        '输入序列包含无效字符，仅允许A/T/G/C/N！': '输入序列包含无效字符，仅允许A/T/G/C/N！',
        '已转换为RNA序列': '已转换为RNA序列',
        '已生成互补序列': '已生成互补序列',
        '已生成反向互补序列': '已生成反向互补序列',
        '已翻译序列': '已翻译序列',
        
        # Translation tab options
        '+1 (正链, 从第1位)': '+1 (正链, 从第1位)',
        '+2 (正链, 从第2位)': '+2 (正链, 从第2位)',
        '+3 (正链, 从第3位)': '+3 (正链, 从第3位)',
        '-1 (反链, 从第1位)': '-1 (反链, 从第1位)',
        '-2 (反链, 从第2位)': '-2 (反链, 从第2位)',
        '-3 (反链, 从第3位)': '-3 (反链, 从第3位)',
        '单字母缩写': '单字母缩写',
        '三字母缩写': '三字母缩写',
        
        # ORF tab options and messages
        '正链': '正链',
        '反链': '反链',
        '正+反链': '正+反链',
        '未找到满足条件的ORF。': '未找到满足条件的ORF。',
        '无ORF': '无ORF',
        '读框': '读框',
        '位置': '位置',
        '长度': '长度',
        '序列': '序列',
        '翻译': '翻译',
        
        # BaseTabWidget UI elements
        '输入序列或上传文件：': '输入序列或上传文件：',
        '粘贴DNA/RNA序列，或点击下方按钮上传文件...': '粘贴DNA/RNA序列，或点击下方按钮上传文件...',
        '上传文件': '上传文件',
        '输出结果：': '输出结果：',
        '导出结果': '导出结果',
        '复制到剪贴板': '复制到剪贴板',
        '运行': '运行',
        
        # Dynamic ORF messages (will be handled specially)
        'ORF_COUNT_PATTERN': '共找到{count}个ORF',
        
        # Statistics labels
        '总序列数': '总序列数',
        '总长度': '总长度',
        '最小长度': '最小长度',
        '最大长度': '最大长度',
    },
    
    'en_US': {
        # Window titles
        'BioSeq Analyzer 生物序列分析器': 'BioSeq Analyzer - Biological Sequence Analysis Tool',
        '错误': 'Error',
        
        # Menu items
        'FASTA工具': 'FASTA Tools',
        '序列长度统计': 'Sequence Length Statistics',
        'ID 简化': 'ID Simplification',
        '序列提取 (按ID)': 'Extract Sequences (by ID)',
        '序列提取 (正则表达式)': 'Extract Sequences (by Regex)',
        '从NCBI下载序列': 'Download from NCBI',
        '批量重命名ID': 'Batch Rename IDs',
        
        'DNA序列分析': 'DNA Analysis',
        '转成RNA': 'Convert to RNA',
        '互补序列': 'Complement Sequence',
        '反向互补序列': 'Reverse Complement',
        '翻译序列': 'Translate Sequence',
        'ORF Finder': 'ORF Finder',
        '桑格测序数据处理': 'Sanger Sequencing Data Processing',
        
        '蛋白质序列分析': 'Protein Analysis',
        '氨基酸组成': 'Amino Acid Composition',
        '物化性质计算': 'Physicochemical Properties',
        '二级结构预测': 'Secondary Structure Prediction',
        '三级结构预测': 'Tertiary Structure Prediction',
        '结构域预测': 'Domain Prediction',
        '信号肽预测': 'Signal Peptide Prediction',
        '跨膜螺旋预测': 'Transmembrane Helix Prediction',
        '同源蛋白搜索': 'Homologous Protein Search',
        '结构相似蛋白搜索': 'Structure Similarity Search',
        
        '序列比对': 'Alignment',
        '双序列比对 (在线工具)': 'Pairwise Alignment (Online Tools)',
        '多序列比对 (在线工具)': 'Multiple Sequence Alignment (Online Tools)',
        '序列标识图 (在线工具)': 'Sequence Logo (Online Tools)',
        
        'BLAST分析': 'BLAST',
        'NCBI在线BLAST': 'NCBI Online BLAST',
        '本地BLAST': 'Local BLAST',
        '1. 构建BLAST数据库...': '1. Build BLAST Database...',
        '2. 运行BLAST查询...': '2. Run BLAST Query...',
        
        '引物设计': 'Primers',
        'PCR 引物设计助手': 'PCR Primer Design Assistant',
        
        '进化树构建与可视化': 'Phylogenetic Tree',
        '系统发育树构建(在线工具)': 'Phylogenetic Tree Construction (Online Tools)',
        '进化树可视化（在线工具）': 'Phylogenetic Tree Visualization (Online Tools)',
        
        '收藏夹': 'Favorites',
        '管理收藏夹': 'Manage Bookmarks',
        
        '设置': 'Settings',
        '外观主题': 'Appearance Theme',
        '浅色主题': 'Light Theme',
        '深色主题': 'Dark Theme',
        '界面语言': 'Interface Language',
        '检查更新': 'Check for Updates',
        '关于': 'About',
        
        # Dialog texts
        '当前版本: v1.0.0\n\n暂无可用更新。\n\n您可以访问项目主页获取最新信息：\nhttps://github.com/yananzh/BioSeq-Analyzer': 
            'Current Version: v1.0.0\n\nNo updates available.\n\nVisit the project homepage for the latest information:\nhttps://github.com/yananzh/BioSeq-Analyzer',
        '关于 BioSeq Analyzer': 'About BioSeq Analyzer',
        
        # Common UI elements
        '输入FASTA文件:': 'Input FASTA File:',
        '选择文件': 'Select File',
        '输出统计文件:': 'Output Statistics File:',
        '输出文件:': 'Output File:',
        '选择位置': 'Choose Location',
        '开始统计': 'Start Analysis',
        '开始简化': 'Start Simplification',
        '开始提取': 'Start Extraction',
        '开始下载': 'Start Download',
        '清空': 'Clear',
        '帮助': 'Help',
        '确定': 'OK',
        '就绪': 'Ready',
        '状态:': 'Status:',
        '操作日志将显示在此处...': 'Operation logs will be displayed here...',
        '已清空': 'Cleared',
        
        # Help dialog titles
        '帮助 - 序列长度统计分析': 'Help - Sequence Length Statistics',
        '帮助 - 序列ID简化': 'Help - Sequence ID Simplification',
        '帮助 - 按ID提取序列': 'Help - Extract Sequences by ID',
        '帮助 - 正则表达式提取序列': 'Help - Extract Sequences by Regex',
        '帮助 - NCBI序列下载': 'Help - NCBI Sequence Download',
        '帮助 - 批量重命名序列ID': 'Help - Batch Rename Sequence IDs',
        
        # Additional UI elements
        '要提取的序列ID列表（每行一个）:': 'Sequence IDs to extract (one per line):',
        '输入序列ID，每行一个\n例如:\nseq1\nseq2\nseq3': 'Enter sequence IDs, one per line\nExample:\nseq1\nseq2\nseq3',
        '正则表达式:': 'Regular Expression:',
        '例如: gene.*protein, ^chr[0-9]+, .*hypothetical.*': 'Example: gene.*protein, ^chr[0-9]+, .*hypothetical.*',
        'ID映射文件:': 'ID Mapping File:',
        '选择映射文件': 'Select Mapping File',
        '映射文件包含标题行': 'Mapping file contains header row',
        '开始重命名': 'Start Renaming',
        '选择FASTA文件': 'Select FASTA File',
        'FASTA文件 (*.fasta *.fa *.fas);;所有文件 (*)': 'FASTA Files (*.fasta *.fa *.fas);;All Files (*)',
        '保存简化后的文件': 'Save Simplified File',
        
        # DNA processing help dialogs
        '转成RNA 帮助': 'Convert to RNA Help',
        '将DNA序列中的T（胸腺嘧啶）替换为U（尿嘧啶），支持IUPAC代码和大小写输入。': 'Replace T (thymine) with U (uracil) in DNA sequences. Supports IUPAC codes and case-insensitive input.',
        '互补序列 帮助': 'Complement Sequence Help',
        '生成DNA的互补序列：A↔T，G↔C，支持IUPAC代码和大小写输入，N保持不变。': 'Generate complement sequence of DNA: A↔T, G↔C. Supports IUPAC codes and case-insensitive input. N remains unchanged.',
        '反向互补序列 帮助': 'Reverse Complement Help',
        '先生成互补序列，再反向排列。常用于分子生物学操作和引物设计。支持IUPAC代码和大小写输入。': 'Generate complement sequence first, then reverse it. Commonly used in molecular biology and primer design. Supports IUPAC codes and case-insensitive input.',
        '翻译序列 帮助': 'Translate Sequence Help',
        '支持DNA/RNA到蛋白质的翻译，6种读框，标准密码子表，支持单/三字母氨基酸缩写。': 'Supports DNA/RNA to protein translation with 6 reading frames, standard codon table, and single/three-letter amino acid abbreviations.',
        'ORF Finder 帮助': 'ORF Finder Help',
        '查找所有可能的开放阅读框，支持最小ORF长度阈值，显示ORF的位置、长度、读框和翻译结果，支持正向和反向链。': 'Find all possible open reading frames with minimum ORF length threshold. Shows ORF position, length, reading frame and translation results for both forward and reverse strands.',
        '桑格测序数据处理': 'Sanger Sequencing Data Processing',
        
        # DNA processing status messages
        '请输入DNA序列！': 'Please enter DNA sequence!',
        '请输入DNA或RNA序列！': 'Please enter DNA or RNA sequence!',
        '输入序列包含无效字符，仅允许A/T/G/C/N等IUPAC代码！': 'Input sequence contains invalid characters. Only A/T/G/C/N and other IUPAC codes are allowed!',
        '输入序列包含无效字符，仅允许A/T/G/C/N！': 'Input sequence contains invalid characters. Only A/T/G/C/N are allowed!',
        '已转换为RNA序列': 'Converted to RNA sequence',
        '已生成互补序列': 'Generated complement sequence',
        '已生成反向互补序列': 'Generated reverse complement sequence',
        '已翻译序列': 'Sequence translated',
        
        # Translation tab options
        '+1 (正链, 从第1位)': '+1 (Forward, from position 1)',
        '+2 (正链, 从第2位)': '+2 (Forward, from position 2)',
        '+3 (正链, 从第3位)': '+3 (Forward, from position 3)',
        '-1 (反链, 从第1位)': '-1 (Reverse, from position 1)',
        '-2 (反链, 从第2位)': '-2 (Reverse, from position 2)',
        '-3 (反链, 从第3位)': '-3 (Reverse, from position 3)',
        '单字母缩写': 'Single letter code',
        '三字母缩写': 'Three letter code',
        
        # ORF tab options and messages
        '正链': 'Forward strand',
        '反链': 'Reverse strand',
        '正+反链': 'Both strands',
        '未找到满足条件的ORF。': 'No ORFs found meeting the criteria.',
        '无ORF': 'No ORF',
        '读框': 'Frame',
        '位置': 'Position',
        '长度': 'Length',
        '序列': 'Sequence',
        '翻译': 'Translation',
        
        # BaseTabWidget UI elements
        '输入序列或上传文件：': 'Input Sequence or Upload File:',
        '粘贴DNA/RNA序列，或点击下方按钮上传文件...': 'Paste DNA/RNA sequence, or click button below to upload file...',
        '上传文件': 'Upload File',
        '输出结果：': 'Output Results:',
        '导出结果': 'Export Results',
        '复制到剪贴板': 'Copy to Clipboard',
        '运行': 'Run',
        
        # Dynamic ORF messages (will be handled specially)
        'ORF_COUNT_PATTERN': 'Found {count} ORFs',
        
        # Statistics labels
        '总序列数': 'Total Sequences',
        '总长度': 'Total Length',
        '最小长度': 'Min Length',
        '最大长度': 'Max Length',
        
        # Additional UI elements
        '数据库:': 'Database:',
        '邮箱地址:': 'Email Address:',
        'NCBI要求提供邮箱地址': 'NCBI requires email address',
    }
}

class Translator:
    """Simple translator class for BioSeq Analyzer"""
    
    def __init__(self):
        self.current_language = 'zh_CN'  # Default to Chinese
    
    def set_language(self, language):
        """Set the current language"""
        if language in TRANSLATIONS:
            self.current_language = language
            return True
        return False
    
    def tr(self, text):
        """Translate text to current language"""
        if self.current_language in TRANSLATIONS:
            return TRANSLATIONS[self.current_language].get(text, text)
        return text
    
    def get_current_language(self):
        """Get current language code"""
        return self.current_language

# Global translator instance
_translator = Translator()

def tr(text):
    """Global translation function"""
    return _translator.tr(text)

def set_language(language):
    """Set global language"""
    return _translator.set_language(language)

def get_current_language():
    """Get current language"""
    return _translator.get_current_language()
