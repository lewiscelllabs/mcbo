#!/usr/bin/env python3
"""
Validate GO annotations against local go.owl.

Fetches GO annotations for genes, then validates that the GO terms
exist in the local go.owl import and are properly typed.
"""

import argparse
import json
from pathlib import Path
from typing import Dict, List, Set, Tuple

try:
    from owlready2 import get_ontology
    OWLREADY_AVAILABLE = True
except ImportError:
    OWLREADY_AVAILABLE = False

from .go_annotations import (
    load_gene_ids_from_csv,
    fetch_go_annotations_batch,
    GO_ASPECTS,
)


def load_go_owl(go_owl_path: Path) -> Tuple[Set[str], Set[str], Dict[str, str]]:
    """Load GO ontology and extract GO term information.
    
    Args:
        go_owl_path: Path to go.owl file
    
    Returns:
        Tuple of (valid_go_ids, biological_process_ids, go_id_to_label)
    """
    if not OWLREADY_AVAILABLE:
        raise ImportError("owlready2 is required for GO validation. Install with: pip install owlready2")
    
    print(f"Loading GO ontology from {go_owl_path}...")
    print("  (this may take a minute - go.owl is large)")
    
    onto = get_ontology(str(go_owl_path)).load()
    
    valid_go_ids = set()
    biological_process_ids = set()
    go_id_to_label = {}
    
    # Extract all GO classes
    for cls in onto.classes():
        # GO URIs look like: http://purl.obolibrary.org/obo/GO_0006915
        uri = str(cls.iri)
        if "GO_" in uri:
            # Extract GO:0006915 format
            go_id = uri.split("GO_")[-1]
            go_id_formatted = f"GO:{go_id}"
            valid_go_ids.add(go_id_formatted)
            
            # Get label if available
            if hasattr(cls, 'label') and cls.label:
                label = cls.label[0] if isinstance(cls.label, list) else cls.label
                go_id_to_label[go_id_formatted] = label
            
            # Check if it's a biological process (subclass of GO:0008150)
            # GO:0008150 is the root of biological_process
            if "GO_0008150" in uri or any("GO_0008150" in str(p.iri) for p in cls.ancestors() if hasattr(p, 'iri')):
                biological_process_ids.add(go_id_formatted)
    
    print(f"  Loaded {len(valid_go_ids)} GO terms")
    print(f"  Found {len(biological_process_ids)} biological process terms")
    
    return valid_go_ids, biological_process_ids, go_id_to_label


def validate_annotations(
    annotations: Dict[str, List[dict]],
    valid_go_ids: Set[str],
    biological_process_ids: Set[str],
    go_id_to_label: Dict[str, str],
) -> Tuple[List[str], List[str]]:
    """Validate GO annotations against loaded GO ontology.
    
    Args:
        annotations: GO annotations from Ensembl
        valid_go_ids: Set of valid GO IDs from go.owl
        biological_process_ids: Set of biological process GO IDs
        go_id_to_label: Mapping of GO IDs to labels from go.owl
    
    Returns:
        Tuple of (errors, warnings)
    """
    errors = []
    warnings = []
    
    total_annotations = 0
    invalid_go_ids = set()
    label_mismatches = []
    non_bp_terms = []
    
    for ensembl_id, go_list in annotations.items():
        for go_ann in go_list:
            total_annotations += 1
            go_id = go_ann["go_id"]
            go_name = go_ann["go_name"]
            aspect = go_ann.get("aspect", "biological_process")
            
            # Check if GO ID exists in go.owl
            if go_id not in valid_go_ids:
                invalid_go_ids.add(go_id)
                errors.append(f"GO term {go_id} from Ensembl not found in go.owl")
            else:
                # Check label consistency
                if go_id in go_id_to_label:
                    owl_label = go_id_to_label[go_id]
                    if owl_label.lower() != go_name.lower():
                        label_mismatches.append({
                            "go_id": go_id,
                            "ensembl_label": go_name,
                            "owl_label": owl_label,
                        })
                        warnings.append(
                            f"Label mismatch for {go_id}: "
                            f"Ensembl='{go_name}' vs go.owl='{owl_label}'"
                        )
                
                # Check if claiming to be biological process but isn't
                if aspect == "biological_process" and go_id not in biological_process_ids:
                    non_bp_terms.append(go_id)
                    warnings.append(
                        f"GO term {go_id} ({go_name}) marked as biological_process "
                        f"but not classified as such in go.owl"
                    )
    
    print(f"\n{'='*60}")
    print(f"Validation Results")
    print(f"{'='*60}")
    print(f"Total annotations validated: {total_annotations}")
    print(f"Invalid GO IDs: {len(invalid_go_ids)}")
    print(f"Label mismatches: {len(label_mismatches)}")
    print(f"Non-BP terms marked as BP: {len(non_bp_terms)}")
    
    if invalid_go_ids:
        print(f"\n❌ {len(invalid_go_ids)} invalid GO IDs found:")
        for go_id in sorted(invalid_go_ids)[:10]:
            print(f"  - {go_id}")
        if len(invalid_go_ids) > 10:
            print(f"  ... and {len(invalid_go_ids) - 10} more")
    
    if label_mismatches:
        print(f"\n⚠️  {len(label_mismatches)} label mismatches (first 5):")
        for mismatch in label_mismatches[:5]:
            print(f"  - {mismatch['go_id']}:")
            print(f"      Ensembl: {mismatch['ensembl_label']}")
            print(f"      go.owl:  {mismatch['owl_label']}")
    
    if non_bp_terms:
        print(f"\n⚠️  {len(non_bp_terms)} terms marked as biological_process but not in BP hierarchy")
    
    return errors, warnings


def main():
    parser = argparse.ArgumentParser(
        description="Validate GO annotations against local go.owl",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Validate GO annotations for genes in gene_annotations.csv
  mcbo-validate-go --gene-annotations data.sample/gene_annotations.csv \\
                   --go-owl ontology/imports/go.owl
  
  # Use cached annotations if available
  mcbo-validate-go --gene-annotations data.sample/gene_annotations.csv \\
                   --go-owl ontology/imports/go.owl \\
                   --cached-annotations data.sample/go_annotations.json
"""
    )
    
    parser.add_argument("--gene-annotations", type=Path, required=True,
                        help="Path to gene_annotations.csv with GeneSymbol,EnsemblGeneID")
    parser.add_argument("--go-owl", type=Path, required=True,
                        help="Path to go.owl for validation")
    parser.add_argument("--cached-annotations", type=Path,
                        help="Use cached GO annotations JSON (skip Ensembl fetch)")
    parser.add_argument("--aspects", nargs="+",
                        default=["biological_process"],
                        choices=["biological_process", "molecular_function", "cellular_component"],
                        help="GO aspects to validate (default: biological_process)")
    
    args = parser.parse_args()
    
    if not OWLREADY_AVAILABLE:
        print("❌ owlready2 is required for GO validation")
        print("   Install with: pip install -e python/[validation]")
        return 1
    
    if not args.go_owl.exists():
        print(f"❌ GO ontology file not found: {args.go_owl}")
        print("   Download with: scripts/download_imports.sh")
        return 1
    
    # Load GO ontology
    valid_go_ids, biological_process_ids, go_id_to_label = load_go_owl(args.go_owl)
    
    # Get GO annotations
    if args.cached_annotations and args.cached_annotations.exists():
        print(f"\nLoading cached GO annotations from {args.cached_annotations}")
        with open(args.cached_annotations) as f:
            go_data = json.load(f)
        annotations = go_data.get("annotations", {})
        gene_mapping = go_data.get("gene_mapping", {})
        print(f"  Loaded annotations for {len(annotations)} genes")
    else:
        print(f"\nLoading gene annotations from {args.gene_annotations}")
        gene_mapping = load_gene_ids_from_csv(args.gene_annotations)
        print(f"  Found {len(gene_mapping)} genes with Ensembl IDs")
        
        if not gene_mapping:
            print("❌ No genes found in input file")
            return 1
        
        print(f"\nFetching GO annotations from Ensembl REST API...")
        print(f"  Aspects: {args.aspects}")
        
        global GO_ASPECTS
        GO_ASPECTS = args.aspects
        
        annotations = fetch_go_annotations_batch(
            list(gene_mapping.values()),
            aspects=args.aspects,
        )
        
        total_terms = sum(len(terms) for terms in annotations.values())
        print(f"  Fetched {total_terms} GO terms for {len(annotations)} genes")
    
    # Validate annotations
    print(f"\nValidating GO annotations against {args.go_owl.name}...")
    errors, warnings = validate_annotations(
        annotations,
        valid_go_ids,
        biological_process_ids,
        go_id_to_label,
    )
    
    # Summary
    print(f"\n{'='*60}")
    if errors:
        print(f"❌ Validation failed with {len(errors)} errors")
        return 1
    elif warnings:
        print(f"⚠️  Validation passed with {len(warnings)} warnings")
        return 0
    else:
        print("✅ Validation passed - all GO terms are valid")
        return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
