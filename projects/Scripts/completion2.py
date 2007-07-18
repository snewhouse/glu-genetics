# -*- coding: utf-8 -*-
'''
File:          completion.py

Authors:       Kevin Jacobs (jacobs@bioinformed.com)
               Xiang Deng    (dengx@mail.nih.gov)

Created:       2006-06-29

Abstract:      Performs completion analysis on genotype data

Requires:      Python 2.5, biozilla

Revision:      $Id: $

Input genodata file format(command line argument)

  sdat
        sdat	l1	l2
        s1	g1	g2

  ldat
        ldat	s1	s2
        l1	g1	g2

  genotriples
        s1	l1	g1


Optional input file to indicate the regions

  regions (-e/--regions)
  [region]
  region1
  [samples]
  s1
  s2
  [loci]
  l1
  l2
  [region]
  region2
  [samples]
  s1
  s2
  s3
  [loci]
  l2
  l3
  l4

Optionsl input file to map the sample/locus to grouping variables

  samplegroup (-g/--samplegroup)
        Samples	Group
        s1	name1

  locusgroup (-G/--locusgroup)
        Samples	Group
        l1	name1
'''

__version__ = '0.2'
__copyright__ = 'Copyright (c) 2006 Science Applications International Corporation ("SAIC"). All rights reserved.'

import sys
import unittest
import csv

from   itertools             import islice
from   textwrap              import fill

from   biozilla.utils        import percent
from   biozilla.fileutils    import load_map,autofile,hyphen
from   biozilla.genodata     import load_genostream
from   biozilla.genoarray    import get_genorepr
from   biozilla.regionparser import load_regions,Regions
from   biozilla.sections     import save_section, SectionWriter, save_metadata_section


def output_summary(out,samcomp,samempty,droppedsam,droppedloc,loccomp,locempty,nonmissing,genos_inf,genos_all):
  '''
  Output completion summary report
  '''

  totalsamples = set(samcomp) | droppedsam
  totalloci    = set(loccomp) | droppedloc
  infsamples   = set(samcomp) - samempty
  infloci      = set(loccomp) - locempty
  out.write('\nSamples     Total: %7d, Empty: %7d, Dropped: %7d, Informative: %7d\n' %
           (len(totalsamples),len(samempty),len(droppedsam),len(infsamples)))
  out.write('Loci        Total: %7d, Empty: %7d, Dropped: %7d, Informative: %7d\n' %
           (len(totalloci),len(locempty),len(droppedloc),len(infloci)))

  out.write('\nGLOBAL GENOTYPE COMPLETION RATE FOR ALL DATA:         %10d / %10d = %5.3f%%\n' % \
           (nonmissing,genos_all,percent(nonmissing,genos_all)))
  out.write('GLOBAL GENOTYPE COMPLETION RATE FOR INFORMATIVE DATA: %10d / %10d = %5.3f%%\n' % \
           (nonmissing,genos_inf,percent(nonmissing,genos_inf)))
  e = ' '*5
  empty = e+'(empty)'

  out.write('\nSamples with no data:\n')
  out.write(fill(', '.join(samempty), initial_indent=e,subsequent_indent=e) or empty)
  out.write('\n')
  out.write('\nLoci with no data:\n')
  out.write(fill(', '.join(locempty), initial_indent=e,subsequent_indent=e) or empty)
  out.write('\n')

  out.write('\nDropped samples:\n')
  out.write(fill(', '.join(droppedsam), initial_indent=e,subsequent_indent=e) or empty)
  out.write('\n')
  out.write('\nDropped loci:\n')
  out.write(fill(', '.join(droppedloc), initial_indent=e,subsequent_indent=e) or empty)
  out.write('\n')


def output_detail(out,name,comp):
  '''
  Output completion detail report by sample/locus or by group
  '''
  out.write('\n\nMISSING GENOTYPES BY %s\n' % name.upper())
  out.write('                                                         Informative                   All\n')
  out.write('  Rank     %-25s  Empty   Dropped     N / Total      %%           N / Total      %%  \n' % name)
  out.write('  -------  -------------------------  ------- ------- -----------------  ------  -----------------  ------\n')

  data = sorted( (vals[0],k,vals[2],vals[3],vals[4],vals[5]) for k,vals in comp.iteritems() )

  for rank,(nonmiss,id,empty,dropped,inf,total) in enumerate(data):
    d = (rank+1,id,empty,dropped,nonmiss,inf,percent(nonmiss,inf),nonmiss,total,percent(nonmiss,total))
    out.write('  %7d  %-25s  %7d %7d %7d / %7d  %6.2f  %7d / %7d  %6.2f\n' % d)


def output_group(out,name,comp):
  '''
  Output completion detail report by sample/locus or by group
  '''
  out.write('\n\nMISSING GENOTYPES BY %s\n' % name.upper())
  out.write('                                                         Informative                   All\n')
  out.write('  Rank     %-17s   Member  Empty   Dropped    N / Total      %%           N / Total      %%  \n' % name)
  out.write('  -------  ------------------  ------- ------- ------- -----------------  ------  -----------------  ------\n')

  data = sorted( (vals[0],k,vals[2],vals[3],vals[4],vals[5],vals[6]) for k,vals in comp.iteritems() )

  for rank,(nonmiss,gname,empty,dropped,inf,total,mtotal) in enumerate(data):
    d = (rank+1,gname,mtotal,empty,dropped,nonmiss,inf,percent(nonmiss,inf),nonmiss,total,percent(nonmiss,total))
    out.write('  %7d  %-17s  %7d %7d %7d %7d / %7d  %6.2f  %7d / %7d  %6.2f\n' % d)


def save_elements(sw, elements, name, type):
  '''
  Writes a section for empty or dropped samples/loci to a file
  '''
  data = [['type', type]] + [[e] for e in elements]
  save_section(sw, name, data)


def save_summary(sw,comp,emptyset,dropped,name):
  '''
  Writes a section for completion summary to a file
  '''
  inf   = set(comp) - emptyset
  total = set(comp) | dropped

  data = [['type',        name],
          ['total',       len(total)],
          ['empty',       len(emptyset)],
          ['dropped',     len(dropped)],
          ['complete',    len(inf)]]

  save_section(sw, 'summary', data)


def save_group(sw, comp, name):
  '''
  Writes a section for completion statistics by specified groups to a file
  '''
  data = sorted( (vals[0],k,vals[2],vals[3],vals[4],vals[5],vals[6]) for k,vals in comp.iteritems() )
  data = [(gname,mtotal,empty,dropped,nonmiss,total) for nonmiss,gname,empty,dropped,inf,total,mtotal in data]
  data = [['data',name],['id','members','empty','dropped','completed','total']] + data
  save_section(sw, 'group', data)


def save_detail(sw, comp, name):
  '''
  Writes a section for completion statistics by sample/locus to a file
  '''
  data = sorted( (vals[0],k,vals[2],vals[3],vals[4],vals[5]) for k,vals in comp.iteritems() )
  data = [(id,1,empty,dropped,nonmiss,total) for nonmiss,id,empty,dropped,inf,total in data]
  data = [['type', name],['id','members', 'empty','dropped','completed','total']] + data
  save_section(sw, 'data', data)


def count_missing(genotriples):
  '''
  Count missing genotype by locus/sample

  @param genotriples: genotype triplets
  @type  genotriples: tuple

  >>> genotriples = ('1420_11', 'rs2070', 17),('1420_12', 'rs2070', 19),('1420_2', 'rs2070', 0)
  >>> count_missing(genotriples)
  ({'1420_2': [0, 1], '1420_11': [1, 0], '1420_12': [1, 0]}, {'rs2070': [2, 1]})
  '''
  samcomp = {}
  loccomp = {}

  for sample,locus,geno in genotriples:
    g = not geno
    samcomp.setdefault(sample,[0,0])[g] += 1
    loccomp.setdefault(locus,[0,0])[g] += 1
  return samcomp,loccomp


def process_expected(regions,loccomp,samcomp,samempty,locempty):
  '''
  Populate the statistics with addtional information
  '''
  for locus,counts in loccomp.iteritems():
    if regions:
      expected = expected_samples(locus,regions)
      stats = calculate(samempty,expected,samcomp,counts)
    else:
      stats = [len(samempty),0,len(samcomp)-len(samempty),len(samcomp),len(samcomp)-sum(counts)]
    loccomp[locus].extend(stats)

  for sample,counts in samcomp.iteritems():
    if regions:
      expected = expected_loci(sample,regions)
      stats = calculate(locempty,expected,loccomp,counts)
    else:
      stats = [len(locempty),0,len(loccomp)-len(locempty),len(loccomp),len(loccomp)-sum(counts)]
    samcomp[sample].extend(stats)

def calculate(emptyset,expected,comp,counts):
  '''
  Compute the additional statistics
  '''
  empty    = len(emptyset & expected)
  dropped  = len(expected - set(comp))
  inf      = sum(counts)  - empty
  total    = len(expected)
  return   [empty,dropped,inf,total]


def expected_samples(locus, regions):
  '''
  Compute the expected sample set per locus

  @param   locus: locus id
  @type    locus: str
  @param regions: list of genotyping regions
  @type  regions: list
  @return       : set of sample ids
  @rtype        : set
  '''
  samples = set()
  for name,rsample,rlocus in regions:
    if locus in rlocus:
      samples.update(rsample)
  return samples


def expected_loci(sample, regions):
  '''
  Compute the expected locus set per sample

  @param  sample: sample id
  @type   sample: str
  @param regions: list of genotyping regions
  @type  regions: list
  @return       : a set of locus ids
  @rtype        : set
  '''
  loci = set()

  for name,rsample,rlocus in regions:
    if sample in rsample:
      loci.update(rlocus)

  return loci


def dropped_all(samcomp,loccomp,regions):
  '''
  Compute dropped samples/loci
  '''
  droppedsam,droppedloc = set(),set()

  def expected_all(regions):
    '''
    Compute all samples/loci to be expected
    '''
    expectedsam_all = set()
    expectedloc_all = set()
    for name,rsample,rlocus in regions:
      expectedsam_all.update(rsample)
      expectedloc_all.update(rlocus)
    return expectedsam_all,expectedloc_all

  if regions:
    expectedsam_all,expectedloc_all = expected_all(regions)
    droppedsam = expectedsam_all-set(samcomp)
    droppedloc = expectedloc_all-set(loccomp)
  return droppedsam,droppedloc


def build_emptyset(counts):
  '''
  Build a set of samples/loci without any genotypes
  '''
  return set(k for k,vals in counts.iteritems() if vals[0]==0)


def completion(genotriples,regions):
  '''
  Compute the completion statistics

  @param  genotriples: genotype triplets
  @type   genotriples: tuple
  @param      regions: list of genotyping regions
  @type       regions: list
  '''
  print >> sys.stderr, '\nComputing completion rates...'

  samcomp,loccomp = count_missing(genotriples)
  samempty  = build_emptyset(samcomp)
  locempty  = build_emptyset(loccomp)

  process_expected(regions,loccomp,samcomp,samempty,locempty)

  # FIXME: Not thrilled by all of the opaque positional references
  nonmissing = sum(vals[0] for vals in samcomp.itervalues())
  genos_inf  = sum(vals[4] for vals in samcomp.itervalues())
  genos_all  = sum(vals[5] for vals in samcomp.itervalues())

  return samcomp,samempty,loccomp,locempty,nonmissing,genos_inf,genos_all


def completion_group(comp,groupmap):
  '''
  Compute the completion statistics to report completion rates by specified groups

  @param      comp: the counts of missing and non-missing genotypes by sample/locus
  @type       comp: dict
  @param  groupmap: map sample/locus ids to grouping variables
  @type   groupmap: dict
  '''
  groupcomp = {}

  for i,g in comp.iteritems():
    group = groupmap.get(i,'default')
    for i in range(6):
      # FIXME: Not thrilled by all of the opaque positional references
      groupcomp.setdefault(group,[0,0,0,0,0,0,0])[i]   += g[i]
    groupcomp.setdefault(group,[0,0,0,0,0,0,0])[6]   += 1

  return groupcomp


def option_parser():
  import optparse

  usage = 'usage: %prog [options] file'
  parser = optparse.OptionParser(usage=usage)

  parser.add_option('-o', '--output',          dest='output',          metavar='FILE', default='-',
                    help='Output of completion report')
  parser.add_option('-l', '--limit',           dest='limit',           metavar='N',    default=0 , type='int',
                    help='Limit the number of genotypes considered to N for testing purposes (default=0 for unlimited)')
  parser.add_option('-e', '--regions', dest='regions', metavar='FILE',
                    help='Regions of genotypes expected to be genotyped. Used to compute overall completion.')
  parser.add_option('-f', '--format',          dest='format',          metavar='NAME',
                    help='Format of the input data. Values=sdat,ldat,hapmap,genotriple')
  parser.add_option('-g', '--samplegroup',     dest='samplegroup',     metavar='FILE',
                    help='Map the sample ids to the grouping variable')
  parser.add_option('-G', '--locusgroup',      dest='locusgroup',      metavar='FILE',
                    help='Map the locus ids to the grouping variable')
  parser.add_option(      '--tabularoutput',   dest='tabularoutput',   metavar='FILE',
                    help='Generate machine readable tabular output of results')
  parser.add_option('-r', '--genorepr',        dest='genorepr',        metavar='REPR', default='snp_acgt',
                    help='Input genotype representations. Values=snp_acgt (default), snp_marker, or generic')

  return parser


class TestCompletion(unittest.TestCase):
  def setUp(self):
    self.regions = [('region1', set(['1420_6','1510_2','1510_3','1420_12']), set(['rs2070','rs619'])),
                    ('region2', set(['1420_6','1510_2','1510_3','1420_8','1420_9','1420_12']), set(['rs6048','rs7100']))]
    self.loci = ['rs619','rs2070','rs6048']
    self.samples = ['1420_12','1420_6','1420_8','1420_9']
    self.samcounts = {'1420_12':[5,1],'1420_6':[5,1],'1420_8':[0,4],'1420_9':[3,4]}

  def test_expected_samples(self):
    results = [set(['1420_6', '1420_12', '1510_2', '1510_3']),
               set(['1420_6', '1420_12', '1510_2', '1510_3']),
               set(['1420_6', '1510_2', '1510_3', '1420_8', '1420_9', '1420_12'])]
    expected = []
    for i,locus in enumerate(self.loci):
      expectedsample = expected_samples(locus,self.regions)
      self.assertEquals(expectedsample, results[i])
      expected.append(expectedsample)
    return expected


  def test_expected_loci(self):
    results = [set(['rs2070', 'rs6048', 'rs619', 'rs7100']),
               set(['rs2070', 'rs6048', 'rs619', 'rs7100']),
               set(['rs6048', 'rs7100']),
               set(['rs6048', 'rs7100'])]
    expected = []
    for i,sample in enumerate(self.samples):
      expectedlocus = expected_loci(sample,self.regions)
      self.assertEquals(expectedlocus, results[i])
      expected.append(expectedlocus)
    return expected



def main():
  parser = option_parser()
  options,args = parser.parse_args()

  if len(args) != 1:
    parser.print_help()
    return

  regions = None
  if options.regions:
    regions = list(load_regions(options.regions))

  infile  = hyphen(args[0],        sys.stdin)
  outfile = autofile(hyphen(options.output, sys.stdout),'w')

  genorepr    = get_genorepr(options.genorepr)
  genostream  = load_genostream(infile,options.format,limit=options.limit,genorepr=genorepr)
  genotriples = genostream.as_genotriples()

  samcomp,samempty,loccomp,locempty,nonmissing,genos_inf,genos_all = completion(genotriples,regions)

  print >> sys.stderr, '\nWriting completion output...'

  droppedsam,droppedloc = dropped_all(samcomp,loccomp,regions)
  output_summary(outfile,samcomp,samempty,droppedsam,droppedloc,loccomp,locempty,nonmissing,genos_inf,genos_all)

  output_detail(outfile,'Samples', samcomp)
  output_detail(outfile,'Loci', loccomp)

  if options.samplegroup:
    samplegroup = load_map(options.samplegroup)
    groupcomp   = completion_group(samcomp,samplegroup)
    output_group(outfile,'Sample Group', groupcomp)

  if options.locusgroup:
    locusgroup = load_map(options.locusgroup)
    groupcomp  = completion_group(loccomp,locusgroup)
    output_group(outfile,'Locus Group', groupcomp)

  if options.tabularoutput:
    sw = SectionWriter(options.tabularoutput)
    save_metadata_section(sw, analysis='completion', analysis_version=__version__, format_version='0.1')
    globalcomp    = set(samcomp)    | set(loccomp)
    globalempty   = set(samempty)   | set(locempty)
    globaldropped = set(droppedsam) | set(droppedloc)
    save_summary(sw,globalcomp,globalempty,globaldropped,'global')
    save_summary(sw,samcomp,samempty,droppedsam,'samples')
    save_summary(sw,loccomp,locempty,droppedloc,'loci')

    if options.samplegroup:
      samplegroup = load_map(options.samplegroup)
      groupcomp = completion_group(samcomp,samplegroup)
      save_group(sw, groupcomp, 'samples')

    if options.locusgroup:
      locusgroup = load_map(options.locusgroup)
      groupcomp = completion_group(loccomp,locusgroup)
      save_group(sw, groupcomp, 'loci')

    save_detail(sw, samcomp, 'samples')
    save_detail(sw, loccomp, 'loci')

    save_elements(sw, locempty,  'empty', 'loci')
    save_elements(sw, samempty,  'empty', 'samples')
    save_elements(sw, droppedsam, 'dropped', 'samples')
    save_elements(sw, droppedloc, 'dropped', 'loci')

  print >> sys.stderr, 'Done.\n'


def _test():
  import doctest
  return doctest.testmod()


if __name__ == '__main__':
  #unittest.main(argv=[sys.argv[0],'-q'])
  _test()
  main()
