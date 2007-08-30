# -*- coding: utf-8 -*-
'''
File:          concordance.py

Authors:       Zhaoming Wang (wangzha@mail.nih.gov)

Created:       June 14, 2006

Abstract:      This utility script runs the concordance check betweeen the reference
               genotypes and genotypes from a comparison set of files.

Compatibility: Python 2.5 and above

Requires:      glu, genomerge

Version:       0.99

Revision:      $Id$
'''

__copyright__ = 'Copyright (c) 2007 Science Applications International Corporation ("SAIC")'
__license__   = 'See GLU license for terms by running: glu license'

import csv
import sys

from   operator          import itemgetter
from   itertools         import islice, chain

from   glu.lib.fileutils import autofile, load_map
from   glu.lib.genolib   import load_genostream, snp
from   glu.lib.remap     import remap_alleles, remap_category
from   glu.lib.hwp       import hwp_exact_biallelic
from   glu.lib.sections  import save_section, SectionWriter, save_metadata_section


SAMPLE_HEADER = ['REFKEY','COMPKEY','CONCORD','DISCORD_HET_HET','DISCORD_HET_HOM','DISCORD_HOM_HET',
                 'DISCORD_HOM_HOM','CONCORDANT_RATE']

LOCUS_HEADER  = SAMPLE_HEADER + ['REF_HWP','COMP_HWP','CONCORD_GENO_PAIR','DISCORD_GENO_PAIR',
                                 'ALLELE_MAP_CATEGORY','ALLELE_MAPS']

def geno_pair_mode(g1,g2):
  return g1.homozygote()*2 + g2.homozygote()


class SampleConcordStat(object):
  def __init__(self):
    self.stats = {}

  def update(self, refgeno, refsample, compgeno, compsample):
    sample = refsample,compsample
    values = self.stats.setdefault(sample, [0,0,0,0,0])
    if refgeno.alleles()==compgeno.alleles():
      values[4]    += 1
    else:
      mode = geno_pair_mode(refgeno,compgeno)
      values[mode] += 1


class LocusConcordStat(object):
  def __init__(self):
    self.stats = {}

  def update(self, refgeno, reflocus, compgeno, complocus):
    locus        = reflocus,complocus
    geno         = refgeno,compgeno
    values       = self.stats.setdefault(locus, {})
    values[geno] = values.get(geno,0) + 1


def generate_sample_output(sampleconcord):
  samplestats = []
  for sample,stats in sampleconcord.stats.iteritems():
    concord = stats[4]
    discord = stats[:4]

    samplestat = [sample[0], sample[1], concord]
    samplestat.extend(discord)
    samplestat.append( '%.6f' % (float(concord)/(concord+sum(discord))) )
    samplestats.append(samplestat)

  samplestats.sort(key=itemgetter(7))

  return samplestats


def output_sample_concordstat(filename, sampleconcord):

  f = csv.writer(autofile(filename, 'w'), dialect='excel-tab')
  f.writerow(SAMPLE_HEADER)
  samplestats = generate_sample_output(sampleconcord)
  totals = [ sum(samplestat[i] for samplestat in samplestats) for i in xrange(2,7) ]
  grand_total = sum(totals)

  if grand_total:
    totals.append( '%.6f' % (float(totals[0])/grand_total) )
  else:
    totals.append('')

  samplestat = ['*','*'] + totals
  samplestats.append(samplestat)
  f.writerows(samplestats)

# FIXME: consolidate with the one in glu.lib.hwp
def count_genos(genos):
  hom1 = hom2 = het = 0
  for g,n in genos.iteritems():
    if g.heterozygote():
      het  = n
    elif hom1:
      hom2 = n
    else:
      hom1 = n

  hom1,hom2 = min(hom1,hom2),max(hom1,hom2)
  return hom1,het,hom2


def generate_locus_output(locusconcord,allelemaps):
  locusstats = []
  for locus,stats in locusconcord.stats.iteritems():
    concord   = 0
    discord   = [0,0,0,0]
    refgenos  = {}
    compgenos = {}

    for (g1,g2),n in stats.iteritems():
      refgenos[g1]  = refgenos.get(g1,0)  + n
      compgenos[g2] = compgenos.get(g2,0) + n
      if g1.alleles()==g2.alleles():
        concord       += n
      else:
        mode = geno_pair_mode(g1,g2)
        discord[mode] += n

    locusstat = [locus[0], locus[1], concord]
    locusstat.extend(discord)
    locusstat.append( '%.6f' % (float(concord)/(concord+sum(discord))) )

    refhwp  = hwp_exact_biallelic(*count_genos(refgenos))
    locusstat.append( '%.6f' % refhwp )
    comphwp = hwp_exact_biallelic(*count_genos(compgenos))
    locusstat.append( '%.6f' % comphwp )

    concordgenos = []
    discordgenos = []
    for (g1,g2),n in stats.iteritems():
      if g1.alleles()==g2.alleles():
        concordgenos.append((snp.to_string(g1),snp.to_string(g2),n))
      else:
        discordgenos.append((snp.to_string(g1),snp.to_string(g2),n))

    locusstat.append( ', '.join( '%s->%s:%4d' % (g1,g2,n) for g1,g2,n in concordgenos ))
    locusstat.append( ', '.join( '%s->%s:%4d' % (g1,g2,n) for g1,g2,n in discordgenos ))

    if allelemaps is not None:
      amap = allelemaps.get(locus[1])
      if amap is not None:
        locusstat.append(remap_category(dict(amap)))
        locusstat.append(', '.join( '%s->%s' % (a,b) for a,b in amap if a and b))
      else:
        locusstat.extend(['',''])

    locusstats.append(locusstat)

  locusstats.sort(key=itemgetter(7))

  return locusstats


def output_locus_concordstat(filename, locusconcord, allelemaps):
  f = csv.writer(autofile(filename, 'w'), dialect='excel-tab')
  f.writerow(LOCUS_HEADER)
  locusstats = generate_locus_output(locusconcord,allelemaps)

  totals = [ sum(locusstat[i] for locusstat in locusstats) for i in xrange(2,7) ]
  grand_total = sum(totals)

  if grand_total:
    totals.append( '%.6f' % (float(totals[0])/sum(totals)) )
  else:
    totals.append('')
  locusstat = ['*','*'] + totals + ['']
  locusstats.append(locusstat)

  f.writerows(locusstats)


def load_reference_genotypes(filename, format, locusset, sampleset, limit):
  data = load_genostream(filename,format,genorepr=snp)
  data = data.transformed(include_samples=sampleset, include_loci=locusset).as_ldat()

  samples = dict( (s,i) for i,s in enumerate(data.samples) )
  loci = []
  genos = []
  for locus,row in data:
    loci.append(locus)
    genos.append(row)

  loci = dict( (l,i) for i,l in enumerate(loci))

  return genos,samples,loci


def load_comparison_genotypes(filename, format, locusset, sampleset, lmapfile, smapfile):
  genos = load_genostream(filename,format,genorepr=snp)
  genos = genos.transformed(rename_samples=smapfile, include_samples=smapfile,
                            rename_loci=lmapfile,    include_loci=lmapfile)
  genos = genos.transformed(include_samples=sampleset, include_loci=locusset)
  return genos.as_genotriples().transformed(filter_missing=True)


def invert_dict(d):
  r = {}
  for key,value in d.iteritems():
    r.setdefault(value, []).append(key)
  return r


def concordance(refgenos,samples,loci,compgenos,sampleeq,locuseq,sampleconcord,locusconcord):
   # Construct identity sample map if one is not specified
   if sampleeq is None:
     sampleeq = dict( (s,[s]) for s in samples )

   # Construct identity locus map if one is not specified
   if locuseq is None:
     locuseq = dict( (l,[l]) for l in loci )

   for refsample in sampleeq:
     sampleeq[refsample] = [ s for s in sampleeq[refsample] if s in samples ]

   for reflocus in locuseq:
     locuseq[reflocus] = [ l for l in locuseq[reflocus] if l in loci ]

   # Assumes missing genotypes are prefiltered
   for sample,locus,compgeno in compgenos:
     if sample not in sampleeq or locus not in locuseq:
       continue

     for refsample in sampleeq[sample]:
       for reflocus in locuseq[locus]:
         i = loci[reflocus]
         j = samples[refsample]

         refgeno = refgenos[i][j]

         if refgeno:
           sampleconcord.update(refgeno, refsample, compgeno, sample)
           locusconcord.update(refgeno, reflocus,  compgeno, locus)


# FIXME: Move to global sequence representation module
def make_remap(amap):
  return dict( ((b1,b2),(c1,c2))  for b1,c1 in amap
                                  for b2,c2 in amap )

complement_map = 'AT','TA','CG','GC',(None,None)


def load_remap_file(allelemapfile):
  # FIXME: Use glu.lib.load_map()?
  mapfile = csv.reader(autofile(allelemapfile), dialect='excel-tab')

  allelemap ={}
  for line in mapfile:
    # Skip blank lines or ones with no locus name
    if not line or not line[0]:
      continue

    # Apply implicit complement to lines that do not specify a remapping
    elif len(line) == 1:
      amap = complement_map

    # Otherwise, parse the list of comma separated items into a geno remap
    # dictionary.
    else:
      amap = [ tuple(reversed(m.split(','))) for m in islice(line,1,None) ] + [(None,None)]

    allelemap[line[0]] = amap

  return allelemap


def build_geno_remap(allelemaps):
  return dict( (locus,make_remap(amap)) for locus,amap in allelemaps.iteritems() )


def remap_genotypes(genos, genomap):
  for sample,locus,geno in genos:
    if locus in genomap:
      geno = genomap[locus].get(geno)
    if geno:
      yield sample,locus,geno


def compute_allele_maps(locusconcord):
  for (reflocus,complocus),stats in locusconcord.stats.iteritems():
    concord,bestmap = remap_alleles(stats)
    yield complocus,bestmap


def output_allele_maps(amap,mapfile):
  w = csv.writer(autofile(mapfile,'w'), dialect='excel-tab')
  for locus,map in amap:
    if any(1 for a,b in map.iteritems() if a!=b):
      w.writerow(list(chain([locus],('%s,%s' % (b,a) for a,b in map.iteritems() ))))


def save_results(sw,locusconcord,sampleconcord,allelemaps):
  locusrows  = generate_locus_output(locusconcord,allelemaps)
  samplerows = generate_sample_output(sampleconcord)

  locusrows   = [LOCUS_HEADER]  + locusrows
  samplerows  = [SAMPLE_HEADER] + samplerows
  save_section(sw, 'sample_concordance', samplerows)
  save_section(sw, 'locus_concordance', locusrows)


def option_parser():
  import optparse
  usage = 'Usage: %prog [options] reference comparison...'

  parser = optparse.OptionParser(usage=usage)

  parser.add_option('--refformat',  dest='refformat', metavar='FILE', default='ldat',
                     help='The file format for reference genotype data. Values=ldat(default)')
  parser.add_option('--compformat', dest='compformat',metavar='FILE', default='hapmap',
                     help='The file format for other(comparison) genotype data. Values=hapmap(default)')
  parser.add_option('-r', '--remap',     dest='remap',     metavar='FILE',
                     help='Determine and output the optimal allele mapping based on greatest concordance')
  parser.add_option('-a', '--allelemap', dest='allelemap', metavar='FILE',
                     help='A list of loci to remap the comparison data alleles to the reference data alleles')
  parser.add_option('-o',           dest='sampleout', metavar='FILE',
                     help='Output the concordant statistics by sample to FILE')
  parser.add_option('-O',           dest='locusout',  metavar='FILE',
                     help='Output the concordant statistics by locus to FILE')
  parser.add_option('--samplemap',  dest='samplemap', metavar='FILE',
                     help='Map the sample ids for the comparison data to the set of ids in the sample equivalence map')
  parser.add_option('--locusmap',   dest='locusmap',  metavar='FILE',
                     help='Map the locus ids for the comparison data to the set of ids in the locus equivalence map')
  parser.add_option('--sampleeq',   dest='sampleeq',  metavar='FILE',
                     help='Equivalence mapping between the sample ids from the comparison data and the reference data')
  parser.add_option('--locuseq',    dest='locuseq',   metavar='FILE',
                     help='Equivalence mapping between the locus ids from the comparison data and the reference data')
  parser.add_option('--tabularoutput', dest='tabularoutput', metavar='FILE',
                     help='Generate machine readable tabular output of results')
  return parser


def main():
  parser = option_parser()
  options,args = parser.parse_args()

  if len(args) < 2:
    parser.print_help()
    return

  # Load equivalence maps as many-to-many mappings between final reference
  # names and final comparison names.  Since we match comparison to reference,
  # the mappings must be inverted before use.
  #
  # FIXME: The current code only implements a 1-to-many mapping that does
  #        not represent the true transitive equivalence state, and is
  #        insufficient for reference sets that contain duplicates.  The
  #        solution is to create an equivalence mapping between two
  #        equivalence sets.
  locuseq = eqlocus = None
  if options.locuseq:
    locuseq = load_map(options.locuseq)
    eqlocus = invert_dict(locuseq)

  sampleeq = eqsample = None
  if options.sampleeq:
    sampleeq = load_map(options.sampleeq)
    eqsample = invert_dict(sampleeq)

  refgenos,samples,loci = load_reference_genotypes(args[0],options.refformat,locuseq,sampleeq,None)

  compgenos = [ load_comparison_genotypes(arg, options.compformat, eqlocus, eqsample,
                options.locusmap, options.samplemap) for arg in args[1:] ]

  if len(compgenos)>1:
    compgenos = chain(*compgenos)
  else:
    compgenos = compgenos[0]

  allelemaps = None
  if options.allelemap:
    allelemaps   = load_remap_file(options.allelemap)
    genomappings = build_geno_remap(allelemaps)
    compgenos    = remap_genotypes(compgenos, genomappings)

  sampleconcord = SampleConcordStat()
  locusconcord  = LocusConcordStat()

  concordance(refgenos,samples,loci,compgenos,eqsample,eqlocus,sampleconcord,locusconcord)

  if options.remap:
    print >> sys.stderr, 'Computing best allele mappings...',
    amap = compute_allele_maps(locusconcord)
    output_allele_maps(amap,options.remap)
    print >> sys.stderr, 'Done.'
    # FIXME: Until multipass analysis is implemented, we must stop here.
    return

  if options.sampleout:
    output_sample_concordstat(options.sampleout,sampleconcord)

  if options.locusout:
    output_locus_concordstat(options.locusout,locusconcord,allelemaps)

  if options.tabularoutput:
    sw = SectionWriter(options.tabularoutput)
    save_metadata_section(sw, analysis='concordance', analysis_version='0.1')
    save_results(sw,locusconcord,sampleconcord,allelemaps)

if __name__=='__main__':
  main()
