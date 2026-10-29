"""Exact dimensions for every gauge Cartan family and higher-D Lorentz labels."""
from copy import deepcopy
import unittest

from bsm_atlas.field_conventions import (
    dimension_a, dimension_d, irrep_dimension, irrep_dimension_label, weyl_dimension)


class RepresentationDimensions(unittest.TestCase):
    def test_sage_weyl_dimension_examples(self):
        # Sage's primary examples use these Bourbaki fundamental-weight labels:
        # https://doc.sagemath.org/html/en/reference/combinat/sage/combinat/root_system/root_system.html#sage.combinat.root_system.root_system.WeylDim
        examples=[
            ('B',[1,0,0],7),('B',[0,1,0],21),('B',[0,0,1],8),('B',[1,0,1],48),
            ('F',[1,0,0,0],52),('F',[0,1,0,0],1274),
            ('F',[0,0,1,0],273),('F',[0,0,0,1],26),
            ('E',[0,0,0,0,0,0],1),('E',[0,1,0,0,0,0],78),
            ('E',[0,0,0,0,0,1],27),('E',[0,0,0,0,0,2],351),
            ('E',[0,0,0,0,1,0],351),('E',[0,0,1,0,0,0],351),
            ('E',[1,0,0,0,0,0],27),('E',[1,0,0,0,0,1],650),
            ('E',[2,0,0,0,0,0],351),
        ]
        for family,labels,dimension in examples:
            with self.subTest(family=family,labels=labels):
                self.assertEqual(weyl_dimension(family,labels),dimension)

    def test_existing_classical_formulas_agree(self):
        for family,ranks,formula in [('A',range(1,8),dimension_a),('D',range(4,9),dimension_d)]:
            for rank in ranks:
                for labels in [[0]*rank,[i%3 for i in range(rank)],
                               [1]+[0]*(rank-1),[0]*(rank-1)+[2],[3]*rank]:
                    with self.subTest(family=family,labels=labels):
                        self.assertEqual(weyl_dimension(family,labels),formula(labels))

    def test_adjoint_dimensions(self):
        for rank in range(2,9):
            self.assertEqual(weyl_dimension('A',[1]+[0]*(rank-2)+[1]),rank*(rank+2))
            self.assertEqual(weyl_dimension('B',[0,2] if rank==2 else [0,1]+[0]*(rank-2)),rank*(2*rank+1))
            self.assertEqual(weyl_dimension('C',[2]+[0]*(rank-1)),rank*(2*rank+1))
            if rank>=4:
                self.assertEqual(weyl_dimension('D',[0,1]+[0]*(rank-2)),rank*(2*rank-1))
        for family,labels,dimension in [
            ('A',[2],3),('D',[0,1,1],15),
            ('E',[0,1,0,0,0,0],78),('E',[1,0,0,0,0,0,0],133),
            ('E',[0,0,0,0,0,0,0,1],248),('F',[1,0,0,0],52),('G',[0,1],14),
        ]:
            self.assertEqual(weyl_dimension(family,labels),dimension)

    def test_higher_dimensional_lorentz_vector_and_spinors(self):
        for family,labels,dimension in [
            ('B',[1,0],5),('B',[0,1],4),
            ('D',[1,0,0],6),('D',[0,1,0],4),('D',[0,0,1],4),
            ('B',[1,0,0],7),('B',[0,0,1],8),
            ('D',[1,0,0,0],8),('D',[0,0,1,0],8),('D',[0,0,0,1],8),
        ]:
            with self.subTest(family=family,labels=labels):
                self.assertEqual(weyl_dimension(family,labels),dimension)

    def test_rho_dimensions_and_trivial_modules(self):
        # dim V_rho = 2^(number of positive roots), independently of root length.
        for family,rank,count in [('A',5,15),('B',4,16),('C',4,16),('D',5,20),
                                  ('E',6,36),('E',7,63),('E',8,120),('F',4,24),('G',2,6)]:
            with self.subTest(family=family,rank=rank):
                dimension=weyl_dimension(family,[1]*rank)
                self.assertIs(type(dimension),int)
                self.assertEqual(dimension,2**count)
                self.assertEqual(weyl_dimension(family,[0]*rank),1)
        self.assertEqual(weyl_dimension('A',[0]*64),1)

    def test_reject_invalid_types_and_highest_weights(self):
        for family,labels in [('U1',[1]),('a',[1]),('A',[]),('B',[1]),('C',[1]),
                              ('D',[1,0]),('E',[0]*5),('F',[0]*3),('G',[0]*3),
                              ('A',[0]*65),('A',[-1]),('A',[True]),('A',[1.0]),
                              ('A',['1']),('A',None),('A','1'),(None,[1])]:
            with self.subTest(family=family,labels=labels):
                with self.assertRaises(ValueError):weyl_dimension(family,labels)

    def test_input_labels_and_existing_displays_stay_unchanged(self):
        labels=[1,0,1];before=deepcopy(labels)
        self.assertEqual(weyl_dimension('B',labels),weyl_dimension('B',tuple(labels)))
        self.assertEqual(labels,before)
        algebra={'type':'C','rank':2}
        self.assertEqual(weyl_dimension('C',[1,0]),4)
        self.assertIsNone(irrep_dimension(algebra,[1,0]))
        self.assertEqual(irrep_dimension_label(algebra,[1,0]),'[1,0]')


if __name__=='__main__':unittest.main()
