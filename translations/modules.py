"""
模块功能翻译 - 各功能模块的界面和标签
"""

MODULE_TRANSLATIONS = {
    'zh_CN': {
        # FASTA工具子菜单
        '序列长度统计': '序列长度统计',
        'ID 简化': 'ID 简化',
        '序列提取 (按ID)': '序列提取 (按ID)',
        '序列提取 (正则表达式)': '序列提取 (正则表达式)',
        '从NCBI下载序列': '从NCBI下载序列',
        '批量重命名ID': '批量重命名ID',
        
        # DNA序列分析子菜单
        '转成RNA': '转成RNA',
        '互补序列': '互补序列',
        '反向互补序列': '反向互补序列',
        '翻译序列': '翻译序列',
        'ORF Finder': 'ORF Finder',
        '桑格测序数据处理': '桑格测序数据处理',
        
        # 蛋白质序列分析子菜单
        '氨基酸组成': '氨基酸组成',
        '物化性质计算': '物化性质计算',
        '二级结构预测': '二级结构预测',
        '三级结构预测': '三级结构预测',
        '结构域预测': '结构域预测',
        '信号肽预测': '信号肽预测',
        '跨膜螺旋预测': '跨膜螺旋预测',
        '同源蛋白搜索': '同源蛋白搜索',
        '结构相似蛋白搜索': '结构相似蛋白搜索',
        
        # 序列比对子菜单
        '双序列比对 (在线工具)': '双序列比对 (在线工具)',
        '多序列比对 (在线工具)': '多序列比对 (在线工具)',
        '序列标识图 (在线工具)': '序列标识图 (在线工具)',
        
        # BLAST分析子菜单
        'NCBI在线BLAST': 'NCBI在线BLAST',
        '本地BLAST': '本地BLAST',
        '1. 构建BLAST数据库...': '1. 构建BLAST数据库...',
        '2. 运行BLAST查询...': '2. 运行BLAST查询...',
        
        # 引物设计
        'PCR 引物设计助手': 'PCR 引物设计助手',
        'PCR 引物设计助手 (PyQt6)': 'PCR 引物设计助手 (PyQt6)',
        '1. 粘贴模板序列 (DNA)': '1. 粘贴模板序列 (DNA)',
        '2. 选择设计模式': '2. 选择设计模式',
        '3. 引物基本参数': '3. 引物基本参数',
        '4. 引物特性参数': '4. 引物特性参数',
        '引物设计结果': '引物设计结果',
        '序列长度: {length} bp': '序列长度: {length} bp',
        '常规引物设计 (扩增内部片段)': '常规引物设计 (扩增内部片段)',
        '特定区域设计 (在指定区域内)': '特定区域设计 (在指定区域内)',
        '全长克隆设计 (扩增完整模板)': '全长克隆设计 (扩增完整模板)',
        '目标区域 (Target Region)': '目标区域 (Target Region)',
        '起始位置:': '起始位置:',
        '结束位置:': '结束位置:',
        '引物长度:': '引物长度:',
        '最小': '最小',
        '最优': '最优',
        '最大': '最大',
        'Tm 值 (°C):': 'Tm 值 (°C):',
        'GC 含量 (%):': 'GC 含量 (%):',
        '产物长度 (bp):': '产物长度 (bp):',
        '返回引物对数量:': '返回引物对数量:',
        '清空结果': '清空结果',
        '导出引物': '导出引物',
        
        # 进化树
        '系统发育树构建(在线工具)': '系统发育树构建(在线工具)',
        '进化树可视化（在线工具）': '进化树可视化（在线工具）',
        
        # 收藏夹
        '管理收藏夹': '管理收藏夹',
        '收藏夹管理器': '收藏夹管理器',
        '添加分类': '添加分类',
        '删除分类': '删除分类',
        '重命名分类': '重命名分类',
        '添加收藏': '添加收藏',
        '编辑收藏': '编辑收藏',
        '删除收藏': '删除收藏',
        '在浏览器中打开': '在浏览器中打开',
        '导入收藏': '导入收藏',
        '导出收藏': '导出收藏',
        '导出为 HTML 书签文件': '导出为 HTML 书签文件',
        
        # 具体功能操作
        '开始统计': '开始统计',
        '开始简化': '开始简化',
        '开始提取': '开始提取',
        '开始下载': '开始下载',
        '开始重命名': '开始重命名',
        '开始分析': '开始分析',
        '开始设计': '开始设计',
        '运行拼接': '运行拼接',
        
        # 统计标签
        '总序列数': '总序列数',
        '总长度': '总长度',
        '最小长度': '最小长度',
        '最大长度': '最大长度',
        '平均长度': '平均长度',
        'GC含量(%)': 'GC含量(%)',
        'N含量(%)': 'N含量(%)',
        
        # ORF相关
        '读框': '读框',
        '位置': '位置',
        '长度': '长度',
        '序列': '序列',
        '翻译': '翻译',
        '正链': '正链',
        '反链': '反链',
        '正+反链': '正+反链',
        
        # 桑格测序
        '质量可视化 (支持.ab1)': '质量可视化 (支持.ab1)',
        '序列选择与导出': '序列选择与导出',
        '序列拼接': '序列拼接',
        '加载 .ab1 文件': '加载 .ab1 文件',
        '正向序列:': '正向序列:',
        '反向序列:': '反向序列:',
        '拼接结果：': '拼接结果：',
        
        # BLAST相关
        '构建本地BLAST数据库': '构建本地BLAST数据库',
        '运行本地BLAST查询': '运行本地BLAST查询',
        '数据库类型:': '数据库类型:',
        '蛋白质 (prot)': '蛋白质 (prot)',
        '核苷酸 (nucl)': '核苷酸 (nucl)',
        '查询序列:': '查询序列:',
        'BLAST程序:': 'BLAST程序:',
        '线程数:': '线程数:',
        '开始构建': '开始构建',
        '开始查询': '开始查询',
    },
    
    'en_US': {
        # FASTA工具子菜单
        '序列长度统计': 'Sequence Length Statistics',
        'ID 简化': 'ID Simplification',
        '序列提取 (按ID)': 'Extract Sequences (by ID)',
        '序列提取 (正则表达式)': 'Extract Sequences (by Regex)',
        '从NCBI下载序列': 'Download from NCBI',
        '批量重命名ID': 'Batch Rename IDs',
        
        # DNA序列分析子菜单
        '转成RNA': 'Convert to RNA',
        '互补序列': 'Complement Sequence',
        '反向互补序列': 'Reverse Complement',
        '翻译序列': 'Translate Sequence',
        'ORF Finder': 'ORF Finder',
        '桑格测序数据处理': 'Sanger Sequencing Data Processing',
        
        # 蛋白质序列分析子菜单
        '氨基酸组成': 'Amino Acid Composition',
        '物化性质计算': 'Physicochemical Properties',
        '二级结构预测': 'Secondary Structure Prediction',
        '三级结构预测': 'Tertiary Structure Prediction',
        '结构域预测': 'Domain Prediction',
        '信号肽预测': 'Signal Peptide Prediction',
        '跨膜螺旋预测': 'Transmembrane Helix Prediction',
        '同源蛋白搜索': 'Homologous Protein Search',
        '结构相似蛋白搜索': 'Structure Similarity Search',
        
        # 序列比对子菜单
        '双序列比对 (在线工具)': 'Pairwise Alignment (Online Tools)',
        '多序列比对 (在线工具)': 'Multiple Sequence Alignment (Online Tools)',
        '序列标识图 (在线工具)': 'Sequence Logo (Online Tools)',
        
        # BLAST分析子菜单
        'NCBI在线BLAST': 'NCBI Online BLAST',
        '本地BLAST': 'Local BLAST',
        '1. 构建BLAST数据库...': '1. Build BLAST Database...',
        '2. 运行BLAST查询...': '2. Run BLAST Query...',
        
        # 引物设计
        'PCR 引物设计助手': 'PCR Primer Design Assistant',
        'PCR 引物设计助手 (PyQt6)': 'PCR Primer Design Assistant (PyQt6)',
        '1. 粘贴模板序列 (DNA)': '1. Paste Template Sequence (DNA)',
        '2. 选择设计模式': '2. Select Design Mode',
        '3. 引物基本参数': '3. Basic Primer Parameters',
        '4. 引物特性参数': '4. Primer Characteristics Parameters',
        '引物设计结果': 'Primer Design Results',
        '序列长度: {length} bp': 'Sequence Length: {length} bp',
        '常规引物设计 (扩增内部片段)': 'Standard Primer Design (amplify internal fragment)',
        '特定区域设计 (在指定区域内)': 'Specific Region Design (within specified region)',
        '全长克隆设计 (扩增完整模板)': 'Full-length Cloning Design (amplify complete template)',
        '目标区域 (Target Region)': 'Target Region',
        '起始位置:': 'Start Position:',
        '结束位置:': 'End Position:',
        '引物长度:': 'Primer Length:',
        '最小': 'Min',
        '最优': 'Opt',
        '最大': 'Max',
        'Tm 值 (°C):': 'Tm Value (°C):',
        'GC 含量 (%):': 'GC Content (%):',
        '产物长度 (bp):': 'Product Length (bp):',
        '返回引物对数量:': 'Number of Primer Pairs to Return:',
        '清空结果': 'Clear Results',
        '导出引物': 'Export Primers',
        
        # 进化树
        '系统发育树构建(在线工具)': 'Phylogenetic Tree Construction (Online Tools)',
        '进化树可视化（在线工具）': 'Phylogenetic Tree Visualization (Online Tools)',
        
        # 收藏夹
        '管理收藏夹': 'Manage Bookmarks',
        '收藏夹管理器': 'Bookmark Manager',
        '添加分类': 'Add Category',
        '删除分类': 'Delete Category',
        '重命名分类': 'Rename Category',
        '添加收藏': 'Add Bookmark',
        '编辑收藏': 'Edit Bookmark',
        '删除收藏': 'Delete Bookmark',
        '在浏览器中打开': 'Open in Browser',
        '导入收藏': 'Import Bookmarks',
        '导出收藏': 'Export Bookmarks',
        '导出为 HTML 书签文件': 'Export as HTML Bookmark File',
        
        # 具体功能操作
        '开始统计': 'Start Analysis',
        '开始简化': 'Start Simplification',
        '开始提取': 'Start Extraction',
        '开始下载': 'Start Download',
        '开始重命名': 'Start Renaming',
        '开始分析': 'Start Analysis',
        '开始设计': 'Start Design',
        '运行拼接': 'Run Assembly',
        
        # 统计标签
        '总序列数': 'Total Sequences',
        '总长度': 'Total Length',
        '最小长度': 'Min Length',
        '最大长度': 'Max Length',
        '平均长度': 'Average Length',
        'GC含量(%)': 'GC Content (%)',
        'N含量(%)': 'N Content (%)',
        
        # ORF相关
        '读框': 'Frame',
        '位置': 'Position',
        '长度': 'Length',
        '序列': 'Sequence',
        '翻译': 'Translation',
        '正链': 'Forward strand',
        '反链': 'Reverse strand',
        '正+反链': 'Both strands',
        
        # 桑格测序
        '质量可视化 (支持.ab1)': 'Quality Visualization (supports .ab1)',
        '序列选择与导出': 'Sequence Selection & Export',
        '序列拼接': 'Sequence Assembly',
        '加载 .ab1 文件': 'Load .ab1 File',
        '正向序列:': 'Forward Sequence:',
        '反向序列:': 'Reverse Sequence:',
        '拼接结果：': 'Assembly Result:',
        
        # BLAST相关
        '构建本地BLAST数据库': 'Build Local BLAST Database',
        '运行本地BLAST查询': 'Run Local BLAST Query',
        '数据库类型:': 'Database Type:',
        '蛋白质 (prot)': 'Protein (prot)',
        '核苷酸 (nucl)': 'Nucleotide (nucl)',
        '查询序列:': 'Query Sequence:',
        'BLAST程序:': 'BLAST Program:',
        '线程数:': 'Number of Threads:',
        '开始构建': 'Start Building',
        '开始查询': 'Start Query',
    }
}
