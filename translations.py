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
        
        # NCBI download specific translations
        '检索号列表（每行一个）:': 'Accession Number List (one per line):',
        '输入检索号，每行一个\n例如:\nNM_001101.5\nNP_001092.1\nAF123456': 'Enter accession numbers, one per line\nExample:\nNM_001101.5\nNP_001092.1\nAF123456',
        '保存下载的序列': 'Save Downloaded Sequences',
        '请输入邮箱地址（NCBI要求）': 'Please enter email address (required by NCBI)',
        '请输入检索号': 'Please enter accession numbers',
        '检索号列表为空': 'Accession number list is empty',
        'NCBI返回错误或未找到序列，请检查数据库类型和检索号是否正确': 'NCBI returned error or sequence not found, please check database type and accession numbers',
        '下载完成，共{seq_count}条序列，已保存到: {output_path}': 'Download completed, {seq_count} sequences saved to: {output_path}',
        '正在验证输入...': 'Validating input...',
        '正在连接NCBI...': 'Connecting to NCBI...',
        '正在下载{count}个序列...': 'Downloading {count} sequences...',
        '正在保存文件...': 'Saving file...',
        '需要安装Biopython库来下载NCBI数据': 'Biopython library is required to download NCBI data',
        '网络连接错误: {error}': 'Network connection error: {error}',
        'NCBI下载错误: {error}': 'NCBI download error: {error}',
        '文件保存失败: {error}': 'File save failed: {error}',
        '下载过程中发生错误: {error}': 'Error occurred during download: {error}',
        '请提供邮箱地址（NCBI要求）': 'Please provide email address (required by NCBI)',
        
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
        
        # NCBI download help text
        'NCBI序列下载工具': 'NCBI Sequence Download Tool',
        '功能说明：': 'Function Description:',
        '根据检索号（Accession Number）从NCBI数据库批量下载序列数据。': 'Batch download sequence data from NCBI database based on accession numbers.',
        '使用方法：': 'Usage:',
        '选择目标数据库（nucleotide或protein）': 'Select target database (nucleotide or protein)',
        '输入有效的邮箱地址（NCBI访问要求）': 'Enter valid email address (required by NCBI)',
        '输入检索号列表（每行一个）': 'Enter accession number list (one per line)',
        '指定下载文件的保存位置': 'Specify download file save location',
        '点击"开始下载"按钮': 'Click "Start Download" button',
        '支持的数据库：': 'Supported Databases:',
        'nucleotide：': 'nucleotide:',
        '核酸序列数据库（DNA/RNA）': 'Nucleic acid sequence database (DNA/RNA)',
        'protein：': 'protein:',
        '蛋白质序列数据库': 'Protein sequence database',
        '检索号格式示例：': 'Accession Number Format Examples:',
        '邮箱要求：': 'Email Requirements:',
        'NCBI要求在API访问时提供有效邮箱地址，用于：': 'NCBI requires a valid email address for API access, used for:',
        '追踪API使用情况': 'Tracking API usage',
        '在过度使用时发送通知': 'Sending notifications for excessive usage',
        '技术问题联系': 'Technical issue contact',
        '应用场景：': 'Application Scenarios:',
        '批量下载已知检索号的序列': 'Batch download sequences with known accession numbers',
        '获取最新版本的参考序列': 'Get latest version of reference sequences',
        '构建本地序列数据集': 'Build local sequence datasets',
        '注意事项：': 'Notes:',
        '请遵守NCBI的使用政策，避免过频请求': 'Please comply with NCBI usage policies, avoid excessive requests',
        '网络连接质量会影响下载速度': 'Network connection quality affects download speed',
        '无效的检索号会被跳过并记录': 'Invalid accession numbers will be skipped and logged',
        '输出格式：': 'Output Format:',
        '下载的序列以标准FASTA格式保存，包含完整的序列信息和描述。': 'Downloaded sequences are saved in standard FASTA format with complete sequence information and descriptions.',
        
        # Sanger sequencing tab
        '质量可视化 (支持.ab1)': 'Quality Visualization (supports .ab1)',
        '加载 .ab1 文件': 'Load .ab1 File',
        '导出图片': 'Export Image',
        '序列选择与导出': 'Sequence Selection & Export',
        '选择区间: ': 'Select Range: ',
        '起始': 'Start',
        '终止': 'End',
        '导出选定序列': 'Export Selected Sequence',
        '序列拼接': 'Sequence Assembly',
        '粘贴正向测序序列': 'Paste forward sequencing sequence',
        '加载正向序列文件': 'Load Forward Sequence File',
        '正向序列:': 'Forward Sequence:',
        '粘贴反向测序序列': 'Paste reverse sequencing sequence',
        '加载反向序列文件': 'Load Reverse Sequence File',
        '反向序列:': 'Reverse Sequence:',
        '运行拼接': 'Run Assembly',
        '拼接结果：': 'Assembly Result:',
        '保存拼接序列到文件': 'Save Assembly to File',
        '选择.ab1文件': 'Select .ab1 File',
        '未加载数据': 'No Data Loaded',
        '请先加载.ab1文件后再导出图片': 'Please load .ab1 file first before exporting image',
        '导出图片': 'Export Image',
        '导出成功': 'Export Successful',
        '图片已保存到: {path}': 'Image saved to: {path}',
        '导出失败': 'Export Failed',
        '区间错误': 'Range Error',
        '请输入有效的起止区间': 'Please enter valid start and end range',
        '导出序列': 'Export Sequence',
        '已导出到: {path}': 'Exported to: {path}',
        '选择序列文件': 'Select Sequence File',
        '输入错误': 'Input Error',
        '请粘贴或加载正向和反向序列': 'Please paste or load forward and reverse sequences',
        '拼接警告': 'Assembly Warning',
        '未检测到明显重叠，直接拼接两端': 'No significant overlap detected, directly joining both ends',
        '无拼接结果': 'No Assembly Result',
        '请先运行拼接': 'Please run assembly first',
        '保存拼接序列': 'Save Assembly Sequence',
        '保存成功': 'Save Successful',
        '已保存到: {path}': 'Saved to: {path}',
        '依赖缺失': 'Missing Dependencies',
        '未安装biopython，无法解析.ab1文件。请先安装biopython。': 'Biopython not installed, cannot parse .ab1 files. Please install biopython first.',
        '文件解析错误': 'File Parsing Error',
        '请先加载.ab1文件': 'Please load .ab1 file first',
        'ab1文件无有效主叫碱基': 'ab1 file has no valid called bases',
        '碱基编号': 'Base Number',
        '荧光信号强度': 'Fluorescence Signal Intensity',
        '文件解析错误: {error}': 'File parsing error: {error}',
        
        # BLAST related translations
        '构建本地BLAST数据库': 'Build Local BLAST Database',
        '浏览...': 'Browse...',
        '输入FASTA文件:': 'Input FASTA File:',
        '蛋白质 (prot)': 'Protein (prot)',
        '核苷酸 (nucl)': 'Nucleotide (nucl)',
        '数据库类型:': 'Database Type:',
        '数据库储存位置:': 'Database Storage Location:',
        '选择目录': 'Select Directory',
        '输出数据库名称:': 'Output Database Name:',
        '开始构建': 'Start Building',
        '首次使用': 'First Time Use',
        '首次使用，请指定BLAST+的bin目录（包含makeblastdb等）': 'First time use, please specify BLAST+ bin directory (containing makeblastdb etc.)',
        '选择BLAST+ bin目录': 'Select BLAST+ bin Directory',
        '选择FASTA文件': 'Select FASTA File',
        '选择数据库储存位置': 'Select Database Storage Location',
        '输入错误': 'Input Error',
        '请选择有效的FASTA文件！': 'Please select a valid FASTA file!',
        '请填写输出数据库名称！': 'Please enter output database name!',
        '请选择数据库储存位置！': 'Please select database storage location!',
        '配置错误': 'Configuration Error',
        'BLAST+ bin目录未配置！': 'BLAST+ bin directory not configured!',
        '正在构建数据库，请稍候...': 'Building database, please wait...',
        '成功': 'Success',
        '数据库构建成功！\\n': 'Database built successfully!\\n',
        '失败': 'Failed',
        '数据库构建失败：\\n': 'Database build failed:\\n',
        
        # BLAST run dialog
        '运行本地BLAST查询': 'Run Local BLAST Query',
        '可粘贴FASTA序列或选择文件': 'Paste FASTA sequence or select file',
        '查询序列:': 'Query Sequence:',
        '选择文件': 'Select File',
        'BLAST程序:': 'BLAST Program:',
        '选择本地数据库:': 'Select Local Database:',
        '线程数:': 'Number of Threads:',
        'NumOfHits:': 'Number of Hits:',
        '请选择输出文件路径': 'Please select output file path',
        '选择输出文件': 'Select Output File',
        '开始查询': 'Start Query',
        '首次使用，请指定BLAST+的bin目录（包含blastp等）': 'First time use, please specify BLAST+ bin directory (containing blastp etc.)',
        '选择数据库主文件': 'Select Database Main File',
        'BLAST数据库主文件 (*)': 'BLAST Database Main File (*)',
        '选择FASTA序列文件': 'Select FASTA Sequence File',
        '选择输出文件': 'Select Output File',
        'TSV文件 (*.tsv);;所有文件 (*)': 'TSV Files (*.tsv);;All Files (*)',
        '请选择本地数据库！': 'Please select a local database!',
        '请填写E-value阈值！': 'Please enter E-value threshold!',
        '线程数必须为正整数！': 'Number of threads must be a positive integer!',
        'NumOfHits必须为正整数！': 'Number of hits must be a positive integer!',
        '无效序列': 'Invalid Sequence',
        '请输入一条有效的FASTA格式查询序列！': 'Please enter a valid FASTA format query sequence!',
        '输出错误': 'Output Error',
        '请选择输出文件路径！': 'Please select output file path!',
        '正在运行BLAST查询，请稍候...': 'Running BLAST query, please wait...',
        'BLAST查询完成！结果已保存到：\\n{path}': 'BLAST query completed! Results saved to:\\n{path}',
        'BLAST查询失败：\\n{msg}': 'BLAST query failed:\\n{msg}',
        
        # BLAST result tab
        'BLAST结果: {filename}': 'BLAST Results: {filename}',
        '导出CSV': 'Export CSV',
        '导出TSV': 'Export TSV',
        '导出HTML': 'Export HTML',
        '解析错误': 'Parsing Error',
        'BLAST XML解析失败: {error}': 'BLAST XML parsing failed: {error}',
        '无数据': 'No Data',
        '没有可导出的结果！': 'No results to export!',
        '导出为{format}': 'Export as {format}',
        'blast_result.{ext}': 'blast_result.{ext}',
        '{format}文件 (*.{ext})': '{format} Files (*.{ext})',
        '导出成功': 'Export Successful',
        '结果已导出: {path}': 'Results exported: {path}',
        '导出为HTML': 'Export as HTML',
        'blast_result.html': 'blast_result.html',
        'HTML文件 (*.html)': 'HTML Files (*.html)',
        
        # Primer design related translations
        'PCR 引物设计助手 (PyQt6)': 'PCR Primer Design Assistant (PyQt6)',
        '1. 粘贴模板序列 (DNA)': '1. Paste Template Sequence (DNA)',
        '在此处粘贴FASTA或原始DNA序列...': 'Paste FASTA or raw DNA sequence here...',
        '序列长度: {length} bp': 'Sequence Length: {length} bp',
        '2. 选择设计模式': '2. Select Design Mode',
        '常规引物设计 (扩增内部片段)': 'Standard Primer Design (amplify internal fragment)',
        '特定区域设计 (在指定区域内)': 'Specific Region Design (within specified region)',
        '全长克隆设计 (扩增完整模板)': 'Full-length Cloning Design (amplify complete template)',
        '目标区域 (Target Region)': 'Target Region',
        '起始位置:': 'Start Position:',
        '结束位置:': 'End Position:',
        '3. 引物基本参数': '3. Basic Primer Parameters',
        '引物长度:': 'Primer Length:',
        '最小': 'Min',
        '最优': 'Opt',
        '最大': 'Max',
        'Tm 值 (°C):': 'Tm Value (°C):',
        'GC 含量 (%):': 'GC Content (%):',
        '产物长度 (bp):': 'Product Length (bp):',
        '返回引物对数量:': 'Number of Primer Pairs to Return:',
        '4. 引物特性参数': '4. Primer Characteristics Parameters',
        '允许聚合 (Poly-X):': 'Allow Poly-X:',
        '盐离子浓度 (mM):': 'Salt Ion Concentration (mM):',
        'DNA 浓度 (nM):': 'DNA Concentration (nM):',
        'dNTP 浓度 (mM):': 'dNTP Concentration (mM):',
        '最大 3\' 末端不匹配:': 'Max 3\' End Mismatch:',
        '最大内部不匹配:': 'Max Internal Mismatch:',
        '开始设计': 'Start Design',
        '清空结果': 'Clear Results',
        '导出引物': 'Export Primers',
        '引物设计结果': 'Primer Design Results',
        '正在调用 Primer3 核心库进行计算...': 'Calling Primer3 core library for calculation...',
        '计算完成。': 'Calculation completed.',
        '发生错误: {error}': 'Error occurred: {error}',
        '未能导入 primer3 库，请先安装: pip install primer3-py': 'Failed to import primer3 library, please install first: pip install primer3-py',
        '请先输入模板序列！': 'Please enter template sequence first!',
        '正在设计引物，请稍候...': 'Designing primers, please wait...',
        '准备就绪。': 'Ready.',
        '引物设计完成': 'Primer Design Completed',
        '找到 {count} 个引物对': 'Found {count} primer pairs',
        '未找到合适的引物对': 'No suitable primer pairs found',
        '检查您的参数设置': 'Check your parameter settings',
        '特定区域范围无效，请检查起始/结束位置。': 'Invalid specific region range, please check start/end positions.',
        '引物对': 'Primer Pair',
        '正向引物': 'Forward Primer',
        '反向引物': 'Reverse Primer',
        '产物大小': 'Product Size',
        '详细信息': 'Details',
        '引物序列': 'Primer Sequence',
        '长度': 'Length',
        '位置': 'Position',
        'GC%': 'GC%',
        '自身二聚体': 'Self Dimer',
        '异源二聚体': 'Hetero Dimer',
        '发夹结构': 'Hairpin',
        '3末端稳定性': '3\' End Stability',
        
        # Favorites manager related translations
        '编辑收藏': 'Edit Bookmark',
        '名称：': 'Name:',
        'URL：': 'URL:',
        '收藏夹管理器': 'Bookmark Manager',
        '分类': 'Categories',
        '收藏项目': 'Bookmarks',
        '添加分类': 'Add Category',
        '删除分类': 'Delete Category',
        '重命名分类': 'Rename Category',
        '添加收藏': 'Add Bookmark',
        '编辑收藏': 'Edit Bookmark',
        '删除收藏': 'Delete Bookmark',
        '在浏览器中打开': 'Open in Browser',
        '导入收藏': 'Import Bookmarks',
        '导出收藏': 'Export Bookmarks',
        '新分类': 'New Category',
        '输入分类名称': 'Enter category name',
        '分类名称': 'Category Name',
        '删除确认': 'Delete Confirmation',
        '将删除分类"{category}"及其下所有收藏，确定吗？': 'Will delete category "{category}" and all bookmarks under it, are you sure?',
        '输入新的分类名称': 'Enter new category name',
        '重命名分类': 'Rename Category',
        '添加新收藏': 'Add New Bookmark',
        '收藏名称': 'Bookmark Name',
        '收藏地址': 'Bookmark URL',
        '请输入收藏名称': 'Please enter bookmark name',
        '请输入收藏地址': 'Please enter bookmark URL',
        '确定删除选中的 {count} 个收藏吗？': 'Are you sure to delete {count} selected bookmarks?',
        '导入JSON收藏文件': 'Import JSON Bookmark File',
        'JSON文件 (*.json)': 'JSON Files (*.json)',
        '导入成功': 'Import Successful',
        '已导入 {count} 个收藏': 'Imported {count} bookmarks',
        '导入失败': 'Import Failed',
        '导入失败: {error}': 'Import failed: {error}',
        '导出收藏到JSON文件': 'Export Bookmarks to JSON File',
        '导出成功': 'Export Successful',
        '收藏已导出到: {path}': 'Bookmarks exported to: {path}',
        '导出失败': 'Export Failed',
        '导出失败: {error}': 'Export failed: {error}',
        
        # Additional favorites manager translations
        '该分类已存在！': 'This category already exists!',
        '分类名不能为空，操作取消。': 'Category name cannot be empty, operation cancelled.',
        '目标分类名已存在，操作取消。': 'Target category name already exists, operation cancelled.',
        '名称与 URL 不能为空。': 'Name and URL cannot be empty.',
        '保存错误': 'Save Error',
        '请先选择一个分类。': 'Please select a category first.',
        '请先选中分类再右键。': 'Please select a category first before right-clicking.',
        '请先选择要重命名的收藏项。': 'Please select a bookmark to rename first.',
        '只能一次重命名一个收藏项。': 'Can only rename one bookmark at a time.',
        '无法打开网址：{url}': 'Cannot open URL: {url}',
        '确定删除选中的 {count} 个收藏吗？': 'Are you sure to delete {count} selected bookmarks?',
        '保存收藏夹失败：{error}': 'Failed to save bookmarks: {error}',
        
        # Additional bookmark manager translations
        '未选择任何收藏项。': 'No bookmarks selected.',
        '目标分类与当前分类相同。': 'Target category is the same as current category.',
        '无法解析拖放数据。': 'Cannot parse drag and drop data.',
        '没有可用的分类，请先创建分类。': 'No categories available, please create a category first.',
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
