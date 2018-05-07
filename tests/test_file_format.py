#
# Copyright (C) 2016-2018 University of Oxford
#
# This file is part of msprime.
#
# msprime is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# msprime is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with msprime.  If not, see <http://www.gnu.org/licenses/>.
#
"""
Test cases for the HDF5 format in msprime.
"""
from __future__ import print_function
from __future__ import division

import os
import tempfile
import unittest

import h5py
import kastore
import numpy as np

import msprime
import _msprime
import tests.tsutil as tsutil


def single_locus_no_mutation_example():
    return msprime.simulate(10, random_seed=10)


def single_locus_with_mutation_example():
    return msprime.simulate(10, mutation_rate=10, random_seed=11)


def multi_locus_with_mutation_example():
    return msprime.simulate(
        10, recombination_rate=1, length=10, mutation_rate=10,
        random_seed=2)


def recurrent_mutation_example():
    ts = msprime.simulate(10, recombination_rate=1, length=10, random_seed=2)
    return tsutil.insert_branch_mutations(ts)


def general_mutation_example():
    ts = msprime.simulate(10, recombination_rate=1, length=10, random_seed=2)
    nodes = msprime.NodeTable()
    edges = msprime.EdgeTable()
    ts.dump_tables(nodes=nodes, edges=edges)
    sites = msprime.SiteTable()
    mutations = msprime.MutationTable()
    sites.add_row(position=0, ancestral_state="A", metadata=b"{}")
    sites.add_row(position=1, ancestral_state="C", metadata=b"{'id':1}")
    mutations.add_row(site=0, node=0, derived_state="T")
    mutations.add_row(site=1, node=0, derived_state="G")
    return msprime.load_tables(
        nodes=nodes, edges=edges, sites=sites, mutations=mutations)


def multichar_mutation_example():
    ts = msprime.simulate(10, recombination_rate=1, length=10, random_seed=2)
    return tsutil.insert_multichar_mutations(ts)


def migration_example():
    n = 10
    t = 1
    population_configurations = [
        msprime.PopulationConfiguration(n // 2),
        msprime.PopulationConfiguration(n // 2),
        msprime.PopulationConfiguration(0),
    ]
    demographic_events = [
        msprime.MassMigration(time=t, source=0, destination=2),
        msprime.MassMigration(time=t, source=1, destination=2),
    ]
    ts = msprime.simulate(
        population_configurations=population_configurations,
        demographic_events=demographic_events,
        random_seed=1)
    return ts


def bottleneck_example():
    return msprime.simulate(
        random_seed=1,
        sample_size=100,
        recombination_rate=0.1,
        length=10,
        demographic_events=[
            msprime.SimpleBottleneck(time=0.01, population=0, proportion=0.75)])


def historical_sample_example():
    return msprime.simulate(
        recombination_rate=0.1,
        length=10,
        random_seed=1,
        samples=[(0, j) for j in range(10)])


def no_provenance_example():
    ts = msprime.simulate(10, random_seed=1)
    tables = ts.dump_tables()
    return msprime.load_tables(nodes=tables.nodes, edges=tables.edges)


def provenance_timestamp_only_example():
    ts = msprime.simulate(10, random_seed=1)
    tables = ts.dump_tables()
    provenances = msprime.ProvenanceTable()
    provenances.add_row(timestamp="12345", record="")
    return msprime.load_tables(
        nodes=tables.nodes, edges=tables.edges, provenances=provenances)


def node_metadata_example():
    ts = msprime.simulate(
        sample_size=100, recombination_rate=0.1, length=10, random_seed=1)
    nodes = msprime.NodeTable()
    edges = msprime.EdgeTable()
    ts.dump_tables(nodes=nodes, edges=edges)
    new_nodes = msprime.NodeTable()
    metadatas = ["n_{}".format(u) for u in range(ts.num_nodes)]
    packed, offset = msprime.pack_strings(metadatas)
    new_nodes.set_columns(
        metadata=packed, metadata_offset=offset, flags=nodes.flags, time=nodes.time)
    return msprime.load_tables(nodes=new_nodes, edges=edges)


def site_metadata_example():
    ts = msprime.simulate(10, length=10, random_seed=2)
    tables = ts.dump_tables()
    for j in range(10):
        tables.sites.add_row(j, ancestral_state="a", metadata=b"1234")
    return msprime.load_tables(**tables.asdict())


def mutation_metadata_example():
    ts = msprime.simulate(10, length=10, random_seed=2)
    tables = ts.dump_tables()
    tables.sites.add_row(0, ancestral_state="a")
    for j in range(10):
        tables.mutations.add_row(
            site=0, node=j, derived_state="t", metadata=b"1234")
    return msprime.load_tables(**tables.asdict())


class TestFileFormat(unittest.TestCase):
    """
    Superclass of file format tests.
    """
    def setUp(self):
        fd, self.temp_file = tempfile.mkstemp(prefix="msp_file_test_")
        os.close(fd)

    def tearDown(self):
        os.unlink(self.temp_file)


class TestLoadLegacyExamples(TestFileFormat):
    """
    Tests using the saved legacy file examples to ensure we can load them.
    """
    def verify_tree_sequence(self, ts):
        # Just some quick checks to make sure the tree sequence makes sense.
        self.assertGreater(ts.sample_size, 0)
        self.assertGreater(ts.num_edges, 0)
        self.assertGreater(ts.num_sites, 0)
        self.assertGreater(ts.num_mutations, 0)
        self.assertGreater(ts.sequence_length, 0)
        for t in ts.trees():
            left, right = t.interval
            self.assertGreater(right, left)
            for site in t.sites():
                self.assertTrue(left <= site.position < right)
                for mut in site.mutations:
                    self.assertEqual(mut.site, site.id)

    @unittest.skip("Add tests for loading HDF5")
    def test_hdf5_error(self):
        msprime.load("tests/data/hdf5-formats/msprime-0.5.0_v10.0.hdf5")

    def test_msprime_v_0_5_0(self):
        ts = msprime.load_legacy("tests/data/hdf5-formats/msprime-0.5.0_v10.0.hdf5")
        self.verify_tree_sequence(ts)

    def test_msprime_v_0_4_0(self):
        ts = msprime.load_legacy("tests/data/hdf5-formats/msprime-0.4.0_v3.1.hdf5")
        self.verify_tree_sequence(ts)

    def test_msprime_v_0_3_0(self):
        ts = msprime.load_legacy("tests/data/hdf5-formats/msprime-0.3.0_v2.0.hdf5")
        self.verify_tree_sequence(ts)


class TestRoundTrip(TestFileFormat):
    """
    Tests if we can round trip convert a tree sequence in memory
    through a V2 file format and a V3 format.
    """
    def verify_tree_sequences_equal(self, ts, tsp):
        t1 = ts.tables
        # We need to sort and squash the edges in the new format because it
        # has gone through an edgesets representation. Simplest way to do this
        # is to call simplify.
        t2 = tsp.simplify().tables
        self.assertEqual(t1.nodes, t2.nodes)
        self.assertEqual(t1.edges, t2.edges)
        self.assertEqual(t1.sites, t2.sites)
        self.assertEqual(t1.mutations, t2.mutations)

    def verify_round_trip(self, ts, version):
        msprime.dump_legacy(ts, self.temp_file, version=version)
        tsp = msprime.load_legacy(self.temp_file)
        self.verify_tree_sequences_equal(ts, tsp)
        tsp.dump(self.temp_file)
        tsp = msprime.load(self.temp_file)
        self.verify_tree_sequences_equal(ts, tsp)

    def verify_malformed_json_v2(self, ts, group_name, attr, bad_json):
        msprime.dump_legacy(ts, self.temp_file, 2)
        # Write some bad JSON to the provenance string.
        root = h5py.File(self.temp_file, "r+")
        group = root[group_name]
        group.attrs[attr] = bad_json
        root.close()
        tsp = msprime.load_legacy(self.temp_file)
        self.verify_tree_sequences_equal(ts, tsp)

    def test_malformed_json_v2(self):
        ts = multi_locus_with_mutation_example()
        for group_name in ["trees", "mutations"]:
            for attr in ["environment", "parameters"]:
                for bad_json in ["", "{", "{},"]:
                    self.verify_malformed_json_v2(ts, group_name, attr, bad_json)

    def test_single_locus_no_mutation(self):
        self.verify_round_trip(single_locus_no_mutation_example(), 2)
        self.verify_round_trip(single_locus_no_mutation_example(), 3)
        self.verify_round_trip(single_locus_no_mutation_example(), 10)

    def test_single_locus_with_mutation(self):
        self.verify_round_trip(single_locus_with_mutation_example(), 2)
        self.verify_round_trip(single_locus_with_mutation_example(), 3)
        self.verify_round_trip(single_locus_with_mutation_example(), 10)

    def test_multi_locus_with_mutation(self):
        self.verify_round_trip(multi_locus_with_mutation_example(), 2)
        self.verify_round_trip(multi_locus_with_mutation_example(), 3)
        self.verify_round_trip(multi_locus_with_mutation_example(), 10)

    def test_migration_example(self):
        self.verify_round_trip(migration_example(), 2)
        self.verify_round_trip(migration_example(), 3)
        self.verify_round_trip(migration_example(), 10)

    def test_bottleneck_example(self):
        self.verify_round_trip(migration_example(), 3)
        self.verify_round_trip(migration_example(), 10)

    def test_no_provenance(self):
        self.verify_round_trip(no_provenance_example(), 10)

    def test_provenance_timestamp_only(self):
        self.verify_round_trip(provenance_timestamp_only_example(), 10)

    def test_recurrent_mutation_example(self):
        ts = recurrent_mutation_example()
        for version in [2, 3]:
            self.assertRaises(
                ValueError, msprime.dump_legacy, ts, self.temp_file, version)
        self.verify_round_trip(ts, 10)

    def test_general_mutation_example(self):
        ts = general_mutation_example()
        for version in [2, 3]:
            self.assertRaises(
                ValueError, msprime.dump_legacy, ts, self.temp_file, version)
        self.verify_round_trip(ts, 10)

    def test_v2_no_samples(self):
        ts = multi_locus_with_mutation_example()
        msprime.dump_legacy(ts, self.temp_file, version=2)
        root = h5py.File(self.temp_file, "r+")
        del root['samples']
        root.close()
        tsp = msprime.load_legacy(self.temp_file)
        self.verify_tree_sequences_equal(ts, tsp)

    def test_duplicate_mutation_positions_single_value(self):
        ts = multi_locus_with_mutation_example()
        for version in [2, 3]:
            msprime.dump_legacy(ts, self.temp_file, version=version)
            root = h5py.File(self.temp_file, "r+")
            root['mutations/position'][:] = 0
            root.close()
            self.assertRaises(
                msprime.DuplicatePositionsError, msprime.load_legacy, self.temp_file)
            tsp = msprime.load_legacy(
                self.temp_file, remove_duplicate_positions=True)
            self.assertEqual(tsp.num_sites, 1)
            sites = list(tsp.sites())
            self.assertEqual(sites[0].position, 0)

    def test_duplicate_mutation_positions(self):
        ts = multi_locus_with_mutation_example()
        for version in [2, 3]:
            msprime.dump_legacy(ts, self.temp_file, version=version)
            root = h5py.File(self.temp_file, "r+")
            position = np.array(root['mutations/position'])
            position[0] = position[1]
            root['mutations/position'][:] = position
            root.close()
            self.assertRaises(
                msprime.DuplicatePositionsError, msprime.load_legacy, self.temp_file)
            tsp = msprime.load_legacy(
                self.temp_file, remove_duplicate_positions=True)
            self.assertEqual(tsp.num_sites, position.shape[0] - 1)
            position_after = list(s.position for s in tsp.sites())
            self.assertEqual(list(position[1:]), position_after)


class TestErrors(TestFileFormat):
    """
    Test various API errors.
    """
    def test_v2_non_binary_records(self):
        demographic_events = [
            msprime.SimpleBottleneck(time=0.01, population=0, proportion=1)
        ]
        ts = msprime.simulate(
            sample_size=10,
            demographic_events=demographic_events,
            random_seed=1)
        self.assertRaises(ValueError, msprime.dump_legacy, ts, self.temp_file, 2)

    def test_unsupported_version(self):
        ts = msprime.simulate(10)
        self.assertRaises(ValueError, msprime.dump_legacy, ts, self.temp_file, version=4)
        # Cannot read current files.
        ts.dump(self.temp_file)
        # Catch Exception here because h5py throws different exceptions on py2 and py3
        self.assertRaises(Exception, msprime.load_legacy, self.temp_file)

    def test_no_version_number(self):
        root = h5py.File(self.temp_file, "w")
        root.attrs["x"] = 0
        root.close()
        self.assertRaises(ValueError, msprime.load_legacy, self.temp_file)


class TestDumpFormat(TestFileFormat):
    """
    Tests on the on-disk file format.
    """

    def verify_metadata(self, group, num_rows):

        self.assertEqual(group["metadata_offset"].dtype, np.uint32)
        metadata_offset = list(group["metadata_offset"])
        metadata_length = 0
        if metadata_offset[-1] > 0:
            self.assertEqual(group["metadata"].dtype, np.int8)
            metadata = list(group["metadata"])
            metadata_length = len(metadata)
            self.assertEqual(metadata_offset[-1], metadata_length)
        else:
            self.assertNotIn("metadata", group)
        self.assertEqual(len(metadata_offset), num_rows + 1)

    def verify_dump_format(self, ts):
        ts.dump(self.temp_file)
        self.assertTrue(os.path.exists(self.temp_file))
        self.assertGreater(os.path.getsize(self.temp_file), 0)
        store = kastore.load(self.temp_file, use_mmap=False)
        # Check the basic root attributes
        format_name = store['format/name']
        self.assertTrue(np.array_equal(
            np.array(bytearray(b"tskit.trees"), dtype=np.int8), format_name))
        format_version = store['format/version']
        self.assertEqual(format_version[0], 11)
        self.assertEqual(format_version[1], 0)
        self.assertEqual(ts.sequence_length, store['sequence_length'][0])

        tables = ts.tables
        self.assertTrue(np.array_equal(tables.nodes.flags, store["nodes/flags"]))
        self.assertTrue(np.array_equal(tables.nodes.time, store["nodes/time"]))
        self.assertTrue(np.array_equal(
            tables.nodes.population, store["nodes/population"]))
        self.assertTrue(np.array_equal(
            tables.nodes.metadata, store["nodes/metadata"]))
        self.assertTrue(np.array_equal(
            tables.nodes.metadata_offset, store["nodes/metadata_offset"]))

        self.assertTrue(np.array_equal(tables.edges.left, store["edges/left"]))
        self.assertTrue(np.array_equal(tables.edges.right, store["edges/right"]))
        self.assertTrue(np.array_equal(tables.edges.parent, store["edges/parent"]))
        self.assertTrue(np.array_equal(tables.edges.child, store["edges/child"]))

        left = tables.edges.left
        right = tables.edges.right
        parent = tables.edges.parent
        child = tables.edges.child
        time = tables.nodes.time
        in_order = sorted(
            range(ts.num_edges),
            key=lambda j: (left[j], time[parent[j]], parent[j], child[j]))
        out_order = sorted(
            range(ts.num_edges),
            key=lambda j: (right[j], -time[parent[j]], -parent[j], -child[j]))
        self.assertTrue(np.array_equal(
            np.array(in_order, dtype=np.int32), store["indexes/edge_insertion_order"]))
        self.assertTrue(np.array_equal(
            np.array(out_order, dtype=np.int32), store["indexes/edge_removal_order"]))

        self.assertTrue(
            np.array_equal(tables.migrations.left, store["migrations/left"]))
        self.assertTrue(
            np.array_equal(tables.migrations.right, store["migrations/right"]))
        self.assertTrue(
            np.array_equal(tables.migrations.node, store["migrations/node"]))
        self.assertTrue(
            np.array_equal(tables.migrations.source, store["migrations/source"]))
        self.assertTrue(
            np.array_equal(tables.migrations.dest, store["migrations/dest"]))
        self.assertTrue(
            np.array_equal(tables.migrations.time, store["migrations/time"]))

        self.assertTrue(np.array_equal(tables.sites.position, store["sites/position"]))
        self.assertTrue(np.array_equal(
            tables.sites.ancestral_state, store["sites/ancestral_state"]))
        self.assertTrue(np.array_equal(
            tables.sites.ancestral_state_offset, store["sites/ancestral_state_offset"]))
        self.assertTrue(np.array_equal(
            tables.sites.metadata, store["sites/metadata"]))
        self.assertTrue(np.array_equal(
            tables.sites.metadata_offset, store["sites/metadata_offset"]))

        self.assertTrue(np.array_equal(tables.mutations.site, store["mutations/site"]))
        self.assertTrue(np.array_equal(tables.mutations.node, store["mutations/node"]))
        self.assertTrue(np.array_equal(
            tables.mutations.parent, store["mutations/parent"]))
        self.assertTrue(np.array_equal(
            tables.mutations.derived_state, store["mutations/derived_state"]))
        self.assertTrue(np.array_equal(
            tables.mutations.derived_state_offset,
            store["mutations/derived_state_offset"]))
        self.assertTrue(np.array_equal(
            tables.mutations.metadata, store["mutations/metadata"]))
        self.assertTrue(np.array_equal(
            tables.mutations.metadata_offset, store["mutations/metadata_offset"]))

        self.assertTrue(np.array_equal(
            tables.provenances.record, store["provenances/record"]))
        self.assertTrue(np.array_equal(
            tables.provenances.record_offset, store["provenances/record_offset"]))
        self.assertTrue(np.array_equal(
            tables.provenances.timestamp, store["provenances/timestamp"]))
        self.assertTrue(np.array_equal(
            tables.provenances.timestamp_offset, store["provenances/timestamp_offset"]))

        store.close()

    def test_single_locus_no_mutation(self):
        self.verify_dump_format(single_locus_no_mutation_example())

    def test_single_locus_with_mutation(self):
        self.verify_dump_format(single_locus_with_mutation_example())

    def test_multi_locus_with_mutation(self):
        self.verify_dump_format(multi_locus_with_mutation_example())

    def test_migration_example(self):
        self.verify_dump_format(migration_example())

    def test_bottleneck_example(self):
        self.verify_dump_format(bottleneck_example())

    def test_historical_sample_example(self):
        self.verify_dump_format(historical_sample_example())

    def test_node_metadata_example(self):
        self.verify_dump_format(node_metadata_example())

    def test_site_metadata_example(self):
        self.verify_dump_format(site_metadata_example())

    def test_mutation_metadata_example(self):
        self.verify_dump_format(mutation_metadata_example())

    def test_general_mutation_example(self):
        self.verify_dump_format(general_mutation_example())

    def test_multichar_mutation_example(self):
        self.verify_dump_format(multichar_mutation_example())


class TestFileFormatErrors(TestFileFormat):
    """
    Tests for errors in the HDF5 format.
    """

    def verify_fields(self, ts):
        ts.dump(self.temp_file)
        with kastore.load(self.temp_file, use_mmap=False) as store:
            all_data = dict(store)
        for key in all_data.keys():
            data = dict(all_data)
            del data[key]
            kastore.dump(data, self.temp_file)
            self.assertRaises(_msprime.FileFormatError, msprime.load, self.temp_file)

    def test_missing_fields(self):
        self.verify_fields(migration_example())

    def test_load_empty_kastore(self):
        kastore.dump({}, self.temp_file)
        self.assertRaises(_msprime.FileFormatError, msprime.load, self.temp_file)

    def test_version_load_error(self):
        ts = msprime.simulate(10)
        for bad_version in [(0, 1), (0, 8), (2, 0)]:
            ts.dump(self.temp_file)
            with kastore.load(self.temp_file, use_mmap=False) as store:
                data = dict(store)
            data["format/version"] = np.array(bad_version, dtype=np.uint32)
            kastore.dump(data, self.temp_file)
            self.assertRaises(_msprime.LibraryError, msprime.load, self.temp_file)

    def test_format_name_error(self):
        ts = msprime.simulate(10)
        for bad_name in ["tskit.tree", "tskit.treesAndOther", "", "x"*100]:
            ts.dump(self.temp_file)
            with kastore.load(self.temp_file, use_mmap=False) as store:
                data = dict(store)
            data["format/name"] = np.array(bytearray(bad_name.encode()), dtype=np.int8)
            kastore.dump(data, self.temp_file)
            self.assertRaises(_msprime.LibraryError, msprime.load, self.temp_file)

    def test_load_bad_formats(self):
        # try loading a bunch of files in various formats.
        # First, check the emtpy file.
        self.assertRaises(_msprime.FileFormatError, msprime.load, self.temp_file)
        # Now some ascii text
        with open(self.temp_file, "wb") as f:
            f.write(b"Some ASCII text")
        self.assertRaises(_msprime.FileFormatError, msprime.load, self.temp_file)
        # Now write 8k of random bytes
        with open(self.temp_file, "wb") as f:
            f.write(os.urandom(8192))
        self.assertRaises(_msprime.FileFormatError, msprime.load, self.temp_file)
