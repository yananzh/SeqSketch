"""
消息翻译 - 错误、警告、提示、状态消息等
"""

MESSAGE_TRANSLATIONS = {
    'zh_CN': {
        # 标准化错误处理消息
        '{context}发生错误: {error}': '{context}发生错误: {error}',
        '错误: {error}': '错误: {error}',
        
        # 通用提示消息
        '请输入DNA序列！': '请输入DNA序列！',
        '请输入DNA或RNA序列！': '请输入DNA或RNA序列！',
        '输入序列包含无效字符，仅允许A/T/G/C/N等IUPAC代码！': '输入序列包含无效字符，仅允许A/T/G/C/N等IUPAC代码！',
        '输入序列包含无效字符，仅允许A/T/G/C/N！': '输入序列包含无效字符，仅允许A/T/G/C/N！',
        
        # 处理状态消息
        '已转换为RNA序列': '已转换为RNA序列',
        '已生成互补序列': '已生成互补序列',
        '已生成反向互补序列': '已生成反向互补序列',
        '已翻译序列': '已翻译序列',
        '未找到满足条件的ORF。': '未找到满足条件的ORF。',
        
        # NCBI下载相关消息
        '检索号列表为空': '检索号列表为空',
        '请提供邮箱地址（NCBI要求）': '请提供邮箱地址（NCBI要求）',
        '需要安装Biopython库来下载NCBI数据': '需要安装Biopython库来下载NCBI数据',
        '网络连接错误: {error}': '网络连接错误: {error}',
        'NCBI下载错误: {error}': 'NCBI下载错误: {error}',
        '文件保存失败: {error}': '文件保存失败: {error}',
        '正在连接NCBI...': '正在连接NCBI...',
        '正在下载{count}个序列...': '正在下载{count}个序列...',
        '正在保存文件...': '正在保存文件...',
        '下载完成，共{seq_count}条序列，已保存到: {output_path}': '下载完成，共{seq_count}条序列，已保存到: {output_path}',
        
        # BLAST相关消息
        '请选择有效的FASTA文件！': '请选择有效的FASTA文件！',
        '请填写输出数据库名称！': '请填写输出数据库名称！',
        '请选择数据库储存位置！': '请选择数据库储存位置！',
        'BLAST+ bin目录未配置！': 'BLAST+ bin目录未配置！',
        '正在构建数据库，请稍候...': '正在构建数据库，请稍候...',
        '数据库构建成功！': '数据库构建成功！',
        '数据库构建失败：': '数据库构建失败：',
        '正在运行BLAST查询，请稍候...': '正在运行BLAST查询，请稍候...',
        'BLAST查询完成！结果已保存到：': 'BLAST查询完成！结果已保存到：',
        'BLAST查询失败：': 'BLAST查询失败：',
        
        # 引物设计消息
        '请先输入模板序列！': '请先输入模板序列！',
        '正在设计引物，请稍候...': '正在设计引物，请稍候...',
        '准备就绪。': '准备就绪。',
        '引物设计完成': '引物设计完成',
        '找到 {count} 个引物对': '找到 {count} 个引物对',
        '未找到合适的引物对': '未找到合适的引物对',
        '检查您的参数设置': '检查您的参数设置',
        '正在调用 Primer3 核心库进行计算...': '正在调用 Primer3 核心库进行计算...',
        '计算完成。': '计算完成。',
        '未能导入 primer3 库，请先安装: pip install primer3-py': '未能导入 primer3 库，请先安装: pip install primer3-py',
        '发生错误: {error}': '发生错误: {error}',
        
        # 收藏夹相关消息
        '该分类已存在！': '该分类已存在！',
        '分类名不能为空，操作取消。': '分类名不能为空，操作取消。',
        '目标分类名已存在，操作取消。': '目标分类名已存在，操作取消。',
        '名称与 URL 不能为空。': '名称与 URL 不能为空。',
        '请先选择一个分类。': '请先选择一个分类。',
        '请先选择要重命名的收藏项。': '请先选择要重命名的收藏项。',
        '只能一次重命名一个收藏项。': '只能一次重命名一个收藏项。',
        '无法打开网址：{url}': '无法打开网址：{url}',
        '确定删除选中的 {count} 个收藏吗？': '确定删除选中的 {count} 个收藏吗？',
        '保存收藏夹失败：{error}': '保存收藏夹失败：{error}',
        '书签已导出为 HTML：\n{path}': '书签已导出为 HTML：\n{path}',
        '错误：{error}': '错误：{error}',
        '未选择任何收藏项。': '未选择任何收藏项。',
        '目标分类与当前分类相同。': '目标分类与当前分类相同。',
        '无法解析拖放数据。': '无法解析拖放数据。',
        '没有可用的分类，请先创建分类。': '没有可用的分类，请先创建分类。',
        
        # 桑格测序相关消息
        '未加载数据': '未加载数据',
        '请先加载.ab1文件后再导出图片': '请先加载.ab1文件后再导出图片',
        '导出成功': '导出成功',
        '图片已保存到: {path}': '图片已保存到: {path}',
        '导出失败': '导出失败',
        '区间错误': '区间错误',
        '请输入有效的起止区间': '请输入有效的起止区间',
        '已导出到: {path}': '已导出到: {path}',
        '输入错误': '输入错误',
        '请粘贴或加载正向和反向序列': '请粘贴或加载正向和反向序列',
        '拼接警告': '拼接警告',
        '未检测到明显重叠，直接拼接两端': '未检测到明显重叠，直接拼接两端',
        '无拼接结果': '无拼接结果',
        '请先运行拼接': '请先运行拼接',
        '保存成功': '保存成功',
        '已保存到: {path}': '已保存到: {path}',
        '依赖缺失': '依赖缺失',
        '未安装biopython，无法解析.ab1文件。请先安装biopython。': '未安装biopython，无法解析.ab1文件。请先安装biopython。',
        '文件解析错误': '文件解析错误',
        '请先加载.ab1文件': '请先加载.ab1文件',
        
        # 默认分类名称
        '学习': '学习',
        '新闻': '新闻',
        '工具': '工具',
    },
    
    'en_US': {
        # 标准化错误处理消息
        '{context}发生错误: {error}': 'Error in {context}: {error}',
        '错误: {error}': 'Error: {error}',
        
        # 通用提示消息
        '请输入DNA序列！': 'Please enter DNA sequence!',
        '请输入DNA或RNA序列！': 'Please enter DNA or RNA sequence!',
        '输入序列包含无效字符，仅允许A/T/G/C/N等IUPAC代码！': 'Input sequence contains invalid characters. Only A/T/G/C/N and other IUPAC codes are allowed!',
        '输入序列包含无效字符，仅允许A/T/G/C/N！': 'Input sequence contains invalid characters. Only A/T/G/C/N are allowed!',
        
        # 处理状态消息
        '已转换为RNA序列': 'Converted to RNA sequence',
        '已生成互补序列': 'Generated complement sequence',
        '已生成反向互补序列': 'Generated reverse complement sequence',
        '已翻译序列': 'Sequence translated',
        '未找到满足条件的ORF。': 'No ORFs found meeting the criteria.',
        
        # NCBI下载相关消息
        '检索号列表为空': 'Accession number list is empty',
        '请提供邮箱地址（NCBI要求）': 'Please provide email address (required by NCBI)',
        '需要安装Biopython库来下载NCBI数据': 'Biopython library is required to download NCBI data',
        '网络连接错误: {error}': 'Network connection error: {error}',
        'NCBI下载错误: {error}': 'NCBI download error: {error}',
        '文件保存失败: {error}': 'File save failed: {error}',
        '正在连接NCBI...': 'Connecting to NCBI...',
        '正在下载{count}个序列...': 'Downloading {count} sequences...',
        '正在保存文件...': 'Saving file...',
        '下载完成，共{seq_count}条序列，已保存到: {output_path}': 'Download completed, {seq_count} sequences saved to: {output_path}',
        
        # BLAST相关消息
        '请选择有效的FASTA文件！': 'Please select a valid FASTA file!',
        '请填写输出数据库名称！': 'Please enter output database name!',
        '请选择数据库储存位置！': 'Please select database storage location!',
        'BLAST+ bin目录未配置！': 'BLAST+ bin directory not configured!',
        '正在构建数据库，请稍候...': 'Building database, please wait...',
        '数据库构建成功！': 'Database built successfully!',
        '数据库构建失败：': 'Database build failed:',
        '正在运行BLAST查询，请稍候...': 'Running BLAST query, please wait...',
        'BLAST查询完成！结果已保存到：': 'BLAST query completed! Results saved to:',
        'BLAST查询失败：': 'BLAST query failed:',
        
        # 引物设计消息
        '请先输入模板序列！': 'Please enter template sequence first!',
        '正在设计引物，请稍候...': 'Designing primers, please wait...',
        '准备就绪。': 'Ready.',
        '引物设计完成': 'Primer Design Completed',
        '找到 {count} 个引物对': 'Found {count} primer pairs',
        '未找到合适的引物对': 'No suitable primer pairs found',
        '检查您的参数设置': 'Check your parameter settings',
        '正在调用 Primer3 核心库进行计算...': 'Calling Primer3 core library for calculation...',
        '计算完成。': 'Calculation completed.',
        '未能导入 primer3 库，请先安装: pip install primer3-py': 'Failed to import primer3 library, please install first: pip install primer3-py',
        '发生错误: {error}': 'Error occurred: {error}',
        
        # 收藏夹相关消息
        '该分类已存在！': 'This category already exists!',
        '分类名不能为空，操作取消。': 'Category name cannot be empty, operation cancelled.',
        '目标分类名已存在，操作取消。': 'Target category name already exists, operation cancelled.',
        '名称与 URL 不能为空。': 'Name and URL cannot be empty.',
        '请先选择一个分类。': 'Please select a category first.',
        '请先选择要重命名的收藏项。': 'Please select a bookmark to rename first.',
        '只能一次重命名一个收藏项。': 'Can only rename one bookmark at a time.',
        '无法打开网址：{url}': 'Cannot open URL: {url}',
        '确定删除选中的 {count} 个收藏吗？': 'Are you sure to delete {count} selected bookmarks?',
        '保存收藏夹失败：{error}': 'Failed to save bookmarks: {error}',
        '书签已导出为 HTML：\n{path}': 'Bookmarks exported as HTML:\n{path}',
        '错误：{error}': 'Error: {error}',
        '未选择任何收藏项。': 'No bookmarks selected.',
        '目标分类与当前分类相同。': 'Target category is the same as current category.',
        '无法解析拖放数据。': 'Cannot parse drag and drop data.',
        '没有可用的分类，请先创建分类。': 'No categories available, please create a category first.',
        
        # 桑格测序相关消息
        '未加载数据': 'No Data Loaded',
        '请先加载.ab1文件后再导出图片': 'Please load .ab1 file first before exporting image',
        '导出成功': 'Export Successful',
        '图片已保存到: {path}': 'Image saved to: {path}',
        '导出失败': 'Export Failed',
        '区间错误': 'Range Error',
        '请输入有效的起止区间': 'Please enter valid start and end range',
        '已导出到: {path}': 'Exported to: {path}',
        '输入错误': 'Input Error',
        '请粘贴或加载正向和反向序列': 'Please paste or load forward and reverse sequences',
        '拼接警告': 'Assembly Warning',
        '未检测到明显重叠，直接拼接两端': 'No significant overlap detected, directly joining both ends',
        '无拼接结果': 'No Assembly Result',
        '请先运行拼接': 'Please run assembly first',
        '保存成功': 'Save Successful',
        '已保存到: {path}': 'Saved to: {path}',
        '依赖缺失': 'Missing Dependencies',
        '未安装biopython，无法解析.ab1文件。请先安装biopython。': 'Biopython not installed, cannot parse .ab1 files. Please install biopython first.',
        '文件解析错误': 'File Parsing Error',
        '请先加载.ab1文件': 'Please load .ab1 file first',
        
        # 默认分类名称
        '学习': 'Learning',
        '新闻': 'News',
        '工具': 'Tools',
    }
}
