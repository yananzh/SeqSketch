"""
FASTA模块使用示例

演示如何使用FASTAProcessor和SequenceAnalyzer模块
"""

from fasta_processor import FASTAProcessor, batch_process_fasta_files
from sequence_analyzer import SequenceAnalyzer
import os


def create_sample_fasta():
    """创建示例FASTA文件"""
    sample_data = """>seq1 Human insulin gene
ATGGCCTTTGGTGCAGGCCTCCTGGCCTCTGCTGGCTGCCTGGCTTCTGCCTCGGCCTCTCAGGCATCA
>seq2 Beta-globin gene
ATGGTGCACCTGACTCCTGAGGAGAAGTCTGCCGTTACTGCCCTGTGGGGCAAGGTGAACGTGGATGAAG
>seq3 Cytochrome C gene
ATGGCGCCCCGAGCGGCGCCGCCGCCGCCGCCGCCGCCGCCGCCGCCGCCGCCGCCGCCGCCGCCGCCGCC
"""
    
    with open("sample.fasta", "w") as f:
        f.write(sample_data)
    
    print("创建示例FASTA文件: sample.fasta")


def demo_fasta_processing():
    """演示FASTA文件处理功能"""
    print("\n=== FASTA文件处理演示 ===")
    
    # 创建处理器
    processor = FASTAProcessor()
    
    # 读取文件
    if processor.read_file("sample.fasta"):
        print(f"成功读取文件，包含 {len(processor.records)} 条序列")
        
        # 验证文件
        is_valid, errors = processor.validate_file()
        print(f"文件验证: {'通过' if is_valid else '失败'}")
        if errors:
            print("错误信息:", errors)
        
        # 获取统计信息
        stats = processor.get_statistics()
        print("\n文件统计信息:")
        for key, value in stats.items():
            if key != 'file_path':
                print(f"  {key}: {value}")
        
        # 显示序列信息
        print("\n序列详细信息:")
        for i, record in enumerate(processor.records, 1):
            print(f"  序列 {i}: {record.header}")
            print(f"    长度: {record.length}")
            print(f"    GC含量: {record.get_gc_content():.2f}%")
            print(f"    碱基组成: {record.get_base_composition()}")
            print()
        
        # 过滤序列
        filtered = processor.filter_sequences(min_length=50, max_gc=60)
        print(f"过滤结果: 找到 {len(filtered)} 条符合条件的序列")
        
        # 搜索序列
        search_results = processor.search_sequences("insulin", case_sensitive=False)
        print(f"搜索'insulin': 找到 {len(search_results)} 条序列")
        
        # 保存处理后的文件
        processor.save_file("processed_sample.fasta")
        print("已保存处理后的文件: processed_sample.fasta")


def demo_sequence_analysis():
    """演示序列分析功能"""
    print("\n=== 序列分析演示 ===")
    
    # 创建分析器
    analyzer = SequenceAnalyzer()
    
    # 示例DNA序列
    dna_sequence = "ATGGCCTTTGGTGCAGGCCTCCTGGCCTCTGCTGGCTGCCTGGCTTCTGCCTCGGCCTCTCAGGCATCA"
    
    # DNA序列分析
    print("DNA序列分析:")
    dna_analysis = analyzer.analyze_dna_sequence(dna_sequence)
    print(f"  长度: {dna_analysis['length']}")
    print(f"  GC含量: {dna_analysis['gc_content']}%")
    print(f"  碱基组成: {dna_analysis['base_composition']}")
    
    # 限制性酶切位点
    print("  限制性酶切位点:")
    for enzyme, positions in dna_analysis['restriction_sites'].items():
        print(f"    {enzyme}: {positions}")
    
    # 重复序列
    print("  重复序列:")
    for repeat in dna_analysis['repeats'][:3]:  # 只显示前3个
        print(f"    {repeat['pattern']} (长度:{repeat['length']}, 出现:{repeat['count']}次)")
    
    # DNA翻译
    print("\nDNA翻译:")
    for frame in [1, 2, 3]:
        protein = analyzer.translate_dna(dna_sequence, frame)
        print(f"  阅读框 {frame}: {protein}")
    
    # 蛋白质序列分析
    protein_sequence = "MKTVRQERLKSIVRILERSKEPVSGAQLAEELSVSRQVIVQDIAYLRSLGYNIVATPRGYVLAGG"
    print(f"\n蛋白质序列分析:")
    protein_analysis = analyzer.analyze_protein_sequence(protein_sequence)
    print(f"  长度: {protein_analysis['length']}")
    print(f"  分子量: {protein_analysis['molecular_weight']} Da")
    print(f"  等电点: {protein_analysis['isoelectric_point']}")
    print(f"  疏水性: {protein_analysis['hydrophobicity']}")
    print(f"  二级结构预测:")
    for structure, percentage in protein_analysis['secondary_structure'].items():
        print(f"    {structure}: {percentage}%")


def demo_sequence_comparison():
    """演示序列比较功能"""
    print("\n=== 序列比较演示 ===")
    
    analyzer = SequenceAnalyzer()
    
    # 两个相似序列
    seq1 = "ATGGCCTTTGGTGCAGGCCTCCTGGCCTCTGCTGGCTGCCTGGCTTCTGCCTCGGCCTCTCAGGCATCA"
    seq2 = "ATGGCCTTTGGTGCAGGCCTCCTGGCCTCTGCTGGCTGCCTGGCTTCTGCCTCGGCCTCTCAGGCATCA"
    
    # 引入一些差异
    seq2 = seq2[:30] + "T" + seq2[31:]
    
    # 计算相似性
    similarity = analyzer.calculate_similarity(seq1, seq2)
    print(f"序列相似性: {similarity['similarity_percentage']}%")
    print(f"匹配位置: {similarity['matches']}")
    print(f"差异位置: {similarity['differences']}")
    print(f"编辑距离: {similarity['edit_distance']}")


def demo_motif_search():
    """演示基序搜索功能"""
    print("\n=== 基序搜索演示 ===")
    
    analyzer = SequenceAnalyzer()
    
    # 示例序列
    sequence = "ATGGCCTTTGGTGCAGGCCTCCTGGCCTCTGCTGGCTGCCTGGCTTCTGCCTCGGCCTCTCAGGCATCA"
    
    # 搜索基序
    motifs = analyzer.find_motifs(sequence, "GCC")
    print(f"找到 'GCC' 基序 {len(motifs)} 个:")
    for motif in motifs:
        print(f"  位置 {motif['start']}-{motif['end']}: {motif['sequence']}")
    
    # 使用正则表达式搜索
    motifs = analyzer.find_motifs(sequence, r"GC{2,}")
    print(f"找到 'GC{2,}' 模式 {len(motifs)} 个:")
    for motif in motifs:
        print(f"  位置 {motif['start']}-{motif['end']}: {motif['sequence']}")


def demo_batch_processing():
    """演示批量处理功能"""
    print("\n=== 批量处理演示 ===")
    
    # 创建多个示例文件
    files = []
    for i in range(3):
        filename = f"sample_{i+1}.fasta"
        with open(filename, "w") as f:
            f.write(f">seq{i+1} Sample sequence {i+1}\n")
            f.write("ATGGCCTTTGGTGCAGGCCTCCTGGCCTCTGCTGGCTGCCTGGCTTCTGCCTCGGCCTCTCAGGCATCA\n")
        files.append(filename)
    
    # 批量处理
    results = batch_process_fasta_files(files, "batch_output")
    
    print("批量处理结果:")
    for file_path, result in results.items():
        print(f"  {file_path}: {result['status']}")
        if result['status'] == 'success':
            print(f"    统计信息: {result['statistics']}")
    
    # 清理临时文件
    for filename in files:
        if os.path.exists(filename):
            os.remove(filename)


def main():
    """主函数"""
    print("BioSeq Analyzer - FASTA模块演示")
    print("=" * 50)
    
    # 创建示例文件
    create_sample_fasta()
    
    # 演示各种功能
    demo_fasta_processing()
    demo_sequence_analysis()
    demo_sequence_comparison()
    demo_motif_search()
    demo_batch_processing()
    
    # 清理文件
    if os.path.exists("sample.fasta"):
        os.remove("sample.fasta")
    if os.path.exists("processed_sample.fasta"):
        os.remove("processed_sample.fasta")
    
    print("\n演示完成！")


if __name__ == "__main__":
    main() 