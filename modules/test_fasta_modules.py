"""
FASTA模块测试文件

测试FASTAProcessor和SequenceAnalyzer模块的功能
"""

import unittest
import tempfile
import os
from fasta_processor import FASTAProcessor, FASTARecord, batch_process_fasta_files
from sequence_analyzer import SequenceAnalyzer


class TestFASTARecord(unittest.TestCase):
    """测试FASTARecord类"""
    
    def setUp(self):
        self.record = FASTARecord(
            header="test_seq",
            sequence="ATGCATGC",
            description="Test sequence"
        )
    
    def test_record_creation(self):
        """测试记录创建"""
        self.assertEqual(self.record.header, "test_seq")
        self.assertEqual(self.record.sequence, "ATGCATGC")
        self.assertEqual(self.record.description, "Test sequence")
        self.assertEqual(self.record.length, 8)
    
    def test_gc_content(self):
        """测试GC含量计算"""
        self.assertEqual(self.record.get_gc_content(), 50.0)
        
        # 测试全AT序列
        at_record = FASTARecord("test", "ATATATAT")
        self.assertEqual(at_record.get_gc_content(), 0.0)
        
        # 测试全GC序列
        gc_record = FASTARecord("test", "GCGCGCGC")
        self.assertEqual(gc_record.get_gc_content(), 100.0)
    
    def test_base_composition(self):
        """测试碱基组成"""
        composition = self.record.get_base_composition()
        expected = {'A': 2, 'T': 2, 'G': 2, 'C': 2}
        self.assertEqual(composition, expected)


class TestFASTAProcessor(unittest.TestCase):
    """测试FASTAProcessor类"""
    
    def setUp(self):
        self.processor = FASTAProcessor()
        self.test_fasta_content = """>seq1 Test sequence 1
ATGCATGCATGC
>seq2 Test sequence 2
GCTAGCTAGCTA
>seq3 Test sequence 3
TATATATATATA
"""
    
    def test_read_file(self):
        """测试文件读取"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.fasta', delete=False) as f:
            f.write(self.test_fasta_content)
            temp_file = f.name
        
        try:
            result = self.processor.read_file(temp_file)
            self.assertTrue(result)
            self.assertEqual(len(self.processor.records), 3)
            self.assertEqual(self.processor.records[0].header, "seq1")
            self.assertEqual(self.processor.records[0].sequence, "ATGCATGCATGC")
        finally:
            os.unlink(temp_file)
    
    def test_validate_file(self):
        """测试文件验证"""
        # 创建有效文件
        with tempfile.NamedTemporaryFile(mode='w', suffix='.fasta', delete=False) as f:
            f.write(self.test_fasta_content)
            temp_file = f.name
        
        try:
            self.processor.read_file(temp_file)
            is_valid, errors = self.processor.validate_file()
            self.assertTrue(is_valid)
            self.assertEqual(len(errors), 0)
        finally:
            os.unlink(temp_file)
        
        # 创建无效文件
        invalid_content = """>seq1
ATGCATGC
>seq2
>seq3
INVALID_CHARS
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.fasta', delete=False) as f:
            f.write(invalid_content)
            temp_file = f.name
        
        try:
            self.processor.read_file(temp_file)
            is_valid, errors = self.processor.validate_file()
            self.assertFalse(is_valid)
            self.assertGreater(len(errors), 0)
        finally:
            os.unlink(temp_file)
    
    def test_get_statistics(self):
        """测试统计信息获取"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.fasta', delete=False) as f:
            f.write(self.test_fasta_content)
            temp_file = f.name
        
        try:
            self.processor.read_file(temp_file)
            stats = self.processor.get_statistics()
            
            self.assertEqual(stats['total_sequences'], 3)
            self.assertEqual(stats['total_length'], 36)
            self.assertEqual(stats['average_length'], 12.0)
            self.assertIn('average_gc_content', stats)
            self.assertIn('base_composition', stats)
        finally:
            os.unlink(temp_file)
    
    def test_filter_sequences(self):
        """测试序列过滤"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.fasta', delete=False) as f:
            f.write(self.test_fasta_content)
            temp_file = f.name
        
        try:
            self.processor.read_file(temp_file)
            
            # 测试长度过滤
            filtered = self.processor.filter_sequences(min_length=10)
            self.assertEqual(len(filtered), 3)
            
            filtered = self.processor.filter_sequences(min_length=15)
            self.assertEqual(len(filtered), 0)
            
            # 测试GC含量过滤
            filtered = self.processor.filter_sequences(min_gc=40)
            self.assertEqual(len(filtered), 2)  # seq1和seq2的GC含量较高
        finally:
            os.unlink(temp_file)
    
    def test_save_file(self):
        """测试文件保存"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.fasta', delete=False) as f:
            f.write(self.test_fasta_content)
            temp_file = f.name
        
        try:
            self.processor.read_file(temp_file)
            
            # 保存文件
            output_file = temp_file + "_output.fasta"
            result = self.processor.save_file(output_file)
            self.assertTrue(result)
            
            # 验证保存的文件
            with open(output_file, 'r') as f:
                content = f.read()
                self.assertIn(">seq1", content)
                self.assertIn("ATGCATGCATGC", content)
            
            os.unlink(output_file)
        finally:
            os.unlink(temp_file)
    
    def test_search_sequences(self):
        """测试序列搜索"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.fasta', delete=False) as f:
            f.write(self.test_fasta_content)
            temp_file = f.name
        
        try:
            self.processor.read_file(temp_file)
            
            # 搜索序列
            results = self.processor.search_sequences("Test")
            self.assertEqual(len(results), 3)
            
            results = self.processor.search_sequences("seq1")
            self.assertEqual(len(results), 1)
            self.assertEqual(results[0].header, "seq1")
        finally:
            os.unlink(temp_file)


class TestSequenceAnalyzer(unittest.TestCase):
    """测试SequenceAnalyzer类"""
    
    def setUp(self):
        self.analyzer = SequenceAnalyzer()
        self.test_dna = "ATGGCCTTTGGTGCAGGCCTCCTGGCCTCTGCTGGCTGCCTGGCTTCTGCCTCGGCCTCTCAGGCATCA"
        self.test_protein = "MKTVRQERLKSIVRILERSKEPVSGAQLAEELSVSRQVIVQDIAYLRSLGYNIVATPRGYVLAGG"
    
    def test_analyze_dna_sequence(self):
        """测试DNA序列分析"""
        analysis = self.analyzer.analyze_dna_sequence(self.test_dna)
        
        self.assertEqual(analysis['length'], 72)
        self.assertIn('gc_content', analysis)
        self.assertIn('base_composition', analysis)
        self.assertIn('repeats', analysis)
        self.assertIn('restriction_sites', analysis)
        
        # 验证碱基组成
        composition = analysis['base_composition']
        total_bases = sum(composition.values())
        self.assertEqual(total_bases, 72)
    
    def test_translate_dna(self):
        """测试DNA翻译"""
        # 测试正向翻译
        protein = self.analyzer.translate_dna(self.test_dna, 1)
        self.assertIsInstance(protein, str)
        self.assertGreater(len(protein), 0)
        
        # 测试不同阅读框
        protein2 = self.analyzer.translate_dna(self.test_dna, 2)
        protein3 = self.analyzer.translate_dna(self.test_dna, 3)
        
        # 不同阅读框应该产生不同的蛋白质序列
        self.assertNotEqual(protein, protein2)
        self.assertNotEqual(protein, protein3)
    
    def test_analyze_protein_sequence(self):
        """测试蛋白质序列分析"""
        analysis = self.analyzer.analyze_protein_sequence(self.test_protein)
        
        self.assertEqual(analysis['length'], 67)
        self.assertIn('amino_acid_composition', analysis)
        self.assertIn('molecular_weight', analysis)
        self.assertIn('isoelectric_point', analysis)
        self.assertIn('hydrophobicity', analysis)
        self.assertIn('secondary_structure', analysis)
        
        # 验证氨基酸组成
        composition = analysis['amino_acid_composition']
        total_aa = sum(composition.values())
        self.assertEqual(total_aa, 67)
    
    def test_calculate_similarity(self):
        """测试序列相似性计算"""
        seq1 = "ATGCATGC"
        seq2 = "ATGCATGC"
        seq3 = "ATGCATGT"
        
        # 完全相同的序列
        similarity = self.analyzer.calculate_similarity(seq1, seq2)
        self.assertEqual(similarity['similarity_percentage'], 100.0)
        self.assertEqual(similarity['matches'], 8)
        self.assertEqual(similarity['differences'], 0)
        
        # 有差异的序列
        similarity = self.analyzer.calculate_similarity(seq1, seq3)
        self.assertEqual(similarity['similarity_percentage'], 87.5)  # 7/8 = 87.5%
        self.assertEqual(similarity['matches'], 7)
        self.assertEqual(similarity['differences'], 1)
    
    def test_find_motifs(self):
        """测试基序搜索"""
        sequence = "ATGCATGCATGC"
        
        # 搜索简单基序
        motifs = self.analyzer.find_motifs(sequence, "ATG")
        self.assertEqual(len(motifs), 3)
        
        # 验证位置
        positions = [motif['start'] for motif in motifs]
        self.assertEqual(positions, [0, 4, 8])
        
        # 搜索正则表达式
        motifs = self.analyzer.find_motifs(sequence, r"AT.{2}")
        self.assertEqual(len(motifs), 3)


class TestBatchProcessing(unittest.TestCase):
    """测试批量处理功能"""
    
    def test_batch_process_fasta_files(self):
        """测试批量处理"""
        # 创建临时文件
        temp_files = []
        for i in range(2):
            with tempfile.NamedTemporaryFile(mode='w', suffix='.fasta', delete=False) as f:
                f.write(f">seq{i+1} Test sequence {i+1}\nATGCATGCATGC\n")
                temp_files.append(f.name)
        
        try:
            # 创建输出目录
            output_dir = tempfile.mkdtemp()
            
            # 批量处理
            results = batch_process_fasta_files(temp_files, output_dir)
            
            # 验证结果
            self.assertEqual(len(results), 2)
            for file_path, result in results.items():
                self.assertEqual(result['status'], 'success')
                self.assertIn('statistics', result)
                self.assertIn('is_valid', result)
            
            # 清理输出目录
            import shutil
            shutil.rmtree(output_dir)
            
        finally:
            # 清理临时文件
            for temp_file in temp_files:
                os.unlink(temp_file)


def run_tests():
    """运行所有测试"""
    # 创建测试套件
    test_suite = unittest.TestSuite()
    
    # 添加测试类
    test_classes = [
        TestFASTARecord,
        TestFASTAProcessor,
        TestSequenceAnalyzer,
        TestBatchProcessing
    ]
    
    for test_class in test_classes:
        tests = unittest.TestLoader().loadTestsFromTestCase(test_class)
        test_suite.addTests(tests)
    
    # 运行测试
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(test_suite)
    
    return result.wasSuccessful()


if __name__ == "__main__":
    print("运行FASTA模块测试...")
    success = run_tests()
    if success:
        print("\n所有测试通过！")
    else:
        print("\n部分测试失败！") 