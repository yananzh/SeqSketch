"""Run a small offline pipeline against the bundled external tools.

Run from the repository root:
py -m scripts.validate_tool_chain --output-dir dist/quality-validation/tool-chain
"""

import argparse
import json
from pathlib import Path

from modules.fasta_processor import FASTAProcessor
from modules.one_step_multigenephy_models import GeneCell, ProjectInput
from modules.one_step_multigenephy_workflow import (
    OneStepMultiGenePhyRunner,
    build_default_tool_adapters,
)
from utils.example_data import example_path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()
    processor = FASTAProcessor()
    if not processor.read_file(example_path("phylo", "cytb_cds_raw.fasta")):
        raise RuntimeError("Teaching dataset could not be read")
    cells = [GeneCell(r.header, "cytb", r.sequence, "sequence", normalized_sequence=r.sequence)
             for r in processor.records]
    project = ProjectInput("offline-example", "", "Strain", ["cytb"],
                           str(Path(args.output_dir).resolve()), iqtree_bootstrap=0, threads="1")
    commands = []
    adapters = build_default_tool_adapters(commands, log_dir=project.output_dir)
    strains = [r.header for r in processor.records]
    first = OneStepMultiGenePhyRunner(adapters, commands).run(project, cells, strains, log_line=print)
    initial_count = len(commands)
    project.resume_mode = "tree"
    second = OneStepMultiGenePhyRunner(adapters, commands).run(project, cells, strains, log_line=print)
    assert len(commands) - initial_count == 1, "Resume reran alignment or trimming"
    assert second.step_status["Concatenate"] == "skipped"
    assert Path(first.artifacts.treefile_path).is_file()
    print(json.dumps({"status": "passed", "versions": second.artifacts.manifest_path,
                      "tree": second.artifacts.treefile_path, "resume_commands": 1}, indent=2))


if __name__ == "__main__":
    main()
