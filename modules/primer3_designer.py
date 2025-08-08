# -*- coding: utf-8 -*-
"""
Optimized PCR Primer Designer logic for integration as a module.
This module provides a class and function to perform primer design using primer3-py.
It is intended to be imported and used by a GUI (such as main_window.py or main.py).
"""
import importlib
try:
    p3_bindings = importlib.import_module("primer3.bindings")
except Exception:
    p3_bindings = None

def is_primer3_available():
    """Check if primer3-py is installed and importable."""
    return p3_bindings is not None

class PrimerDesignError(Exception):
    pass

class PrimerDesigner:
    """
    Encapsulates primer design logic for use in GUI or scripts.
    """
    def __init__(self):
        if not is_primer3_available():
            raise PrimerDesignError("primer3-py is not installed. Please install with: pip install primer3-py")

    def design_primers(self, sequence, mode="standard", region=None, product_size_range=(150, 300), num_primers=5,
                       primer_len=(18, 20, 25), primer_tm=(57.0, 60.0, 63.0), primer_gc=(40.0, 50.0, 60.0)):
        """
        Design PCR primers for the given sequence and parameters.
        Args:
            sequence (str): DNA sequence (FASTA or raw, uppercase recommended)
            mode (str): 'standard', 'specific', or 'cloning'
            region (tuple): (start, end) for 'specific' mode (1-based, inclusive)
            product_size_range (tuple): (min, max) product size
            num_primers (int): Number of primer pairs to return
            primer_len (tuple): (min, opt, max) primer length
            primer_tm (tuple): (min, opt, max) primer Tm
            primer_gc (tuple): (min, opt, max) primer GC percent
        Returns:
            dict: Results from primer3-py
        Raises:
            PrimerDesignError: If input is invalid or primer3 fails
        """
        if not sequence or not isinstance(sequence, str):
            raise PrimerDesignError("Invalid DNA sequence.")
        sequence = sequence.strip().upper()
        seq_len = len(sequence)
        if seq_len < 50:
            raise PrimerDesignError("Sequence too short for primer design (min 50bp).")
        seq_args = {
            'SEQUENCE_ID': 'Template',
            'SEQUENCE_TEMPLATE': sequence
        }
        global_args = {
            'PRIMER_OPT_SIZE': primer_len[1],
            'PRIMER_MIN_SIZE': primer_len[0],
            'PRIMER_MAX_SIZE': primer_len[2],
            'PRIMER_OPT_TM': primer_tm[1],
            'PRIMER_MIN_TM': primer_tm[0],
            'PRIMER_MAX_TM': primer_tm[2],
            'PRIMER_MIN_GC': primer_gc[0],
            'PRIMER_MAX_GC': primer_gc[2],
            'PRIMER_OPT_GC_PERCENT': primer_gc[1],
            'PRIMER_NUM_RETURN': num_primers,
            'PRIMER_EXPLAIN_FLAG': 1,
        }
        if mode == "specific":
            if not region or len(region) != 2:
                raise PrimerDesignError("Region must be (start, end) for specific mode.")
            start, end = region
            if start < 1 or end > seq_len or start >= end:
                raise PrimerDesignError("Invalid region range.")
            # primer3 expects a comma-separated string for SEQUENCE_INCLUDED_REGION
            seq_args['SEQUENCE_INCLUDED_REGION'] = f"{start - 1},{end - start + 1}"
            global_args['PRIMER_PRODUCT_SIZE_RANGE'] = [product_size_range[0], product_size_range[1]]
        elif mode == "cloning":
            # primer3 expects a comma-separated string for SEQUENCE_TARGET
            seq_args['SEQUENCE_TARGET'] = f"0,{seq_len}"
            global_args['PRIMER_PRODUCT_SIZE_RANGE'] = [max(50, seq_len - 50), seq_len + 50]
        else:  # standard
            global_args['PRIMER_PRODUCT_SIZE_RANGE'] = [product_size_range[0], product_size_range[1]]
        if p3_bindings is None:
            raise PrimerDesignError("primer3-py is not installed or failed to import.")
        try:
            results = p3_bindings.designPrimers(seq_args=seq_args, global_args=global_args)
            return results
        except Exception as e:
            raise PrimerDesignError(f"primer3-py error: {str(e)}")
