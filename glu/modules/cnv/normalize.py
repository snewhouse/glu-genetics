# -*- coding: utf-8 -*-

from __future__ import division

__gluindex__  = True
__abstract__  = 'Perform quantile normalization and re-estimate LRR and BAF'
__copyright__ = 'Copyright (c) 2011, BioInformed LLC and the U.S. Department of Health & Human Services. Funded by NCI under Contract N01-CO-12400.'
__license__   = 'See GLU license for terms by running: glu license'
__revision__  = '$Id$'


import os

from   math                 import modf

import numpy as np

from   glu.lib.glm          import Linear
from   glu.lib.progressbar  import progress_loop

from   glu.modules.cnv.gdat import GDATFile, BatchTableWriter, parallel_gdat_iter, create_gdat_qn, get_gcmodel


def boxcox(x,l=0,d=0,base=None):
  '''
  Shifted Box-Cox Power Transformation

  l    : lambda         (default=0)
  d    : delta          (defailt=0)
  base : logarithm base (default=e)

  See: http://en.wikipedia.org/wiki/Power_transform
       http://www.jstor.org/pss/2984418
  '''
  assert l>=0

  x = x.astype(float)-d

  if l==0:
    y = np.log(x)
  else:
    y = (x**l-1)/l

  if base is not None:
    y /= np.log(base)

  return y


def gmpt(x,l=0,d=0,base=np.e):
  '''
  General Modulus Power Transformation

  l    : lambda         (default=0)
  d    : delta          (defailt=0)
  base : logarithm base (default=e)

  See: http://en.wikipedia.org/wiki/Power_transform
       http://www.informaworld.com/smpp/content~db=all~content=a780040516

  '''
  assert l>=0

  x = np.asarray(x, dtype=float)

  if l==0:
    y = np.sign(x)*np.log(np.abs(x)+1)
  else:
    y = np.sign(x)*((np.abs(x)+1)**l-1)/l

  if base!=np.e:
    y /= np.log(base)

  return y


def quantile(data,k):
  mask = np.isfinite(data)
  data = data[mask]

  data.sort()

  n    = len(data)-1
  f,w  = modf(n*k)
  w    = int(w)

  if f < 1e-10:
    q  = data[w]
  else:
    q  = (1-f)*data[w] + f*data[w+1]

  return q


def quantile_normalize(x,y,min_threshold=None,max_threshold=None):
  if min_threshold is not None:
    xmin     = min_threshold*x
    ymin     = min_threshold*y

  if max_threshold is not None:
    xmax     = max_threshold*x
    ymax     = max_threshold*y

  mask       = np.isfinite(x)
  mask      &= np.isfinite(y)

  xx         = x[mask]
  yy         = y[mask]

  xorder     = xx.argsort()
  yorder     = yy.argsort()

  values     = xx[xorder]+yy[yorder]
  values    /= 2.0

  xx[xorder] = values
  yy[yorder] = values

  x[mask]    = xx
  y[mask]    = yy

  if min_threshold is not None:
    np.maximum(x,xmin,out=x)
    np.maximum(y,ymin,out=y)

  if max_threshold is not None:
    np.minimum(x,xmax,out=x)
    np.minimum(y,ymax,out=y)

  return x,y


def outlier_mask(data):
  mask    = np.isfinite(data)
  valid   = data[mask]

  if len(valid)<20:
    return mask|(~mask)

  valid.sort()

  n       = valid.shape[0]
  vmin    = np.min(valid[ 5],valid[int(n*0.01)])
  vmax    = np.max(valid[-5],valid[int(n*0.99)])

  outlier = (~mask)|(data<vmin)|(data>vmax)

  return outlier


def trimmed_mean(data, p):
  mask    = np.isfinite(data)
  valid   = data[mask]
  valid.sort()
  n       = valid.shape[0]
  lower   = int(p*n)
  upper   = n-lower
  return valid[lower:upper].mean(axis=0)


def compute_lrr_baf(t,r,r_AA,r_AB,r_BB,t_AA,t_AB,t_BB):
  # Set assays with no observed hets to use average of two
  # homozygotes for r and theta
  mask    = np.isfinite(t_AA)&np.isfinite(t_BB)&(~np.isfinite(t_AB))
  t_AB[mask] = (t_AA[mask]+t_BB[mask])/2.0
  r_AB[mask] = (r_AA[mask]+r_BB[mask])/2.0

  t0      = t <= t_AA
  t1      = t >  t_AA
  t1     &= t <= t_AB
  t2      = t >  t_AB
  t2     &= t <  t_BB
  t3      = t >= t_BB

  mAA_AB  = t    - t_AA
  mAA_AB /= t_AB - t_AA
  mAB_BB  = t    - t_AB
  mAB_BB /= t_BB - t_AB

  rex1    = r_AB - r_AA
  rex1   *= mAA_AB
  rex1   += r_AA

  rex2    = r_BB - r_AB
  rex2   *= mAB_BB
  rex2   += r_AB

  baf1    = mAA_AB / 2
  baf2    = mAB_BB
  baf2   += 1
  baf2   /= 2

  rex     = np.empty_like(r)
  rex.fill(np.nan)

  rex[t1] = rex1[t1]
  rex[t2] = rex2[t2]
  rex[t0] = r_AA[t0]
  rex[t3] = r_BB[t3]

  rex    += 1e-6
  lrr     = np.log2(r/rex)

  if 0:
    print '  t_AA',t_AA[:10]
    print '  t_AB',t_AB[:10]
    print '  t_BB',t_BB[:10]
    print '  r_AA',r_AA[:10]
    print '  r_AB',r_AB[:10]
    print '  r_BB',r_BB[:10]
    print '     t',t[:10]
    print '     r',r[:10]
    print '   rex',rex[:10]
    print '   lrr',lrr[:10]

  baf     = np.empty_like(t)
  baf.fill(np.nan)

  baf[t1] = baf1[t1]
  baf[t2] = baf2[t2]
  baf[t0] = 0
  baf[t3] = 1

  return lrr,baf


def update_centers(r,t,g,r_g,t_g,n_g,genos,mask):
  mask       = (genos==g)&mask
  n_g       +=   mask
  r_g[mask] += r[mask]
  t_g[mask] += t[mask]


def finalize_centers(r_g,t_g,n_g):
  r_g       /= n_g
  t_g       /= n_g


def regress_intensity(x, y, design, dmask, genos, r_AA, r_AB, r_BB, rmodel='linear', thin=None, minpoints=10000):
  AA           = genos=='AA'
  AB           = genos=='AB'
  BB           = genos=='BB'

  valid        = genos!='  '
  valid       &= np.isfinite(x+y)
  valid       &= dmask

  if rmodel=='linear':
    design[:,1]= x
    design[:,2]= y
  elif rmodel=='quadratic':
    design[:,1]= x
    design[:,2]= x*x
    design[:,3]= y
    design[:,4]= y*y
  else:
    raise ValueError('Invalid intensity correction model')

  r_geno       = np.empty_like(x)
  r_geno[AA]   = r_AA[AA]
  r_geno[AB]   = r_AB[AB]
  r_geno[BB]   = r_BB[BB]

  valid       &= np.isfinite(r_geno)

  n            = valid.sum()

  if n<minpoints:
    r          = x+y
    r[~dmask]  = np.nan
    return r

  if thin and n/thin<minpoints:
    thin       = n//minpoints

  r_geno       = r_geno[valid].reshape(-1,1)
  design_valid = design[valid]

  if thin:
    lm = Linear(r_geno[::thin], design_valid[::thin])
  else:
    lm = Linear(r_geno, design_valid)

  lm.fit()

  #print '  R correct: r2=%.2f, p=%s' % (lm.r2(),lm.p_values(phred=True))

  r            = np.empty_like(x)
  r.fill(np.nan)

  valid        = np.isfinite(x+y)&dmask
  r[valid]     = np.dot(design[valid],lm.beta)

  return r


def option_parser():
  from glu.lib.glu_argparse import GLUArgumentParser

  parser = GLUArgumentParser(description=__abstract__)

  parser.add_argument('gdat',                         help='Input GDAT file')

  parser.add_argument('--rmodel',     metavar='NAME', default='quadratic', choices=['linear','quadratic'],
                         help='Intensity correction model: linear or quadratic (default)')
  parser.add_argument('--gcmodel',    metavar='GCM',  help='GC model file to use')
  parser.add_argument('--gcmodeldir', metavar='DIR',  help='GC models directory')
  parser.add_argument('--maxmissing', metavar='RATE', default=0.02, type=float,
                         help='Maximum missing rate for assays to estimate cluster centers (default=0.02)')
  parser.add_argument('--minqual',    metavar='QUANTILE', default=0.10, type=float,
                         help='Minimum genotype quality score (GC) quantile (default=0.10)')
  parser.add_argument('-P', '--progress', action='store_true',
                         help='Show analysis progress bar, if possible')

  return parser


def main():
  parser    = option_parser()
  options   = parser.parse_args()

  if options.rmodel=='linear':
    extra_terms = 2
  elif options.rmodel=='quadratic':
    extra_terms = 4
  else:
    raise ValueError('Invalid intensity correction model')

  gccorrect = bool(options.gcmodel or options.gcmodeldir)

  gdat      = GDATFile(options.gdat,'r+')
  n         = gdat.sample_count
  s         = gdat.snp_count
  qnorm     = True

  create_gdat_qn(gdat,s,n)

  if gccorrect:
    manifest = os.path.splitext(os.path.basename(gdat.attrs['ManifestName']))[0]
    print 'Loading GC/CpG model for %s...' % manifest
    filename = options.gcmodel or '%s/%s.gcm' % (options.gcmodeldir,manifest)

    design,dmask = get_gcmodel(filename, extra_terms=extra_terms)
  else:
    design  = np.ones( (s,1+extra_terms), dtype=float )
    dmask   = design[:,0]==1

  X         = gdat['X']
  Y         = gdat['Y']
  GC        = gdat['GC']
  genotypes = gdat['Genotype']

  print 'SNPs=%d, samples=%d' % (s,n)

  np.set_printoptions(linewidth=120,precision=2,suppress=True)
  np.seterr(all='ignore')

  print 'PASS 1: Re-estimate cluster centers...'

  n_AA        = np.zeros(s, dtype=int  )
  r_AA        = np.zeros(s, dtype=float)
  t_AA        = np.zeros(s, dtype=float)
  n_AB        = np.zeros(s, dtype=int  )
  r_AB        = np.zeros(s, dtype=float)
  t_AB        = np.zeros(s, dtype=float)
  n_BB        = np.zeros(s, dtype=int  )
  r_BB        = np.zeros(s, dtype=float)
  t_BB        = np.zeros(s, dtype=float)

  skipped     = 0

  pass1 = enumerate(parallel_gdat_iter(X,Y,genotypes,GC))

  if options.progress:
    pass1 = progress_loop(pass1, length=n, units='samples', label='PASS 1: ')

  for i,(x,y,genos,gqual) in pass1:
    if not options.progress:
      print '  Sample %5d / %d' % (i+1,n)

    min_qual  = quantile(gqual,options.minqual)

    qmask     = gqual>=min_qual
    qmask    &= dmask

    missing   = (genos=='  ').sum() / s

    if missing > options.maxmissing:
      #print '  ... skipping due to missing rate %.2f%% > %.2f%%' % (missing*100,options.maxmissing*100)
      skipped += 1
      continue

    if qnorm:
      x,y     = quantile_normalize(x,y,max_threshold=1.5)

    r         = x+y
    t         = (2/np.pi)*np.arctan2(y,x)

    mask      = np.isfinite(r)&np.isfinite(t)

    update_centers(r,t,'AA',r_AA,t_AA,n_AA,genos,mask)
    update_centers(r,t,'AB',r_AB,t_AB,n_AB,genos,mask)
    update_centers(r,t,'BB',r_BB,t_BB,n_BB,genos,mask)

  finalize_centers(r_AA,t_AA,n_AA)
  finalize_centers(r_AB,t_AB,n_AB)
  finalize_centers(r_BB,t_BB,n_BB)

  if skipped:
    print '  Skipped %d samples (%.2f%%) for missing rate > %.2f%%' % (skipped,skipped/n*100,options.maxmissing*100)

  print 'PASS 2: Updating LRR and BAF...'

  bad         = t_AA>=t_AB
  bad        |= t_AB>=t_BB
  bad        |= t_AA>=t_BB

  t_AA[bad]   = np.nan
  t_AB[bad]   = np.nan
  t_BB[bad]   = np.nan

  LRR_QN = BatchTableWriter(gdat['LRR_QN'])
  BAF_QN = BatchTableWriter(gdat['BAF_QN'])

  pass2 = enumerate(parallel_gdat_iter(X,Y,genotypes))

  if options.progress:
    pass2 = progress_loop(pass2, length=n, units='samples', label='PASS 2: ')

  for i,(x,y,genos) in pass2:
    if not options.progress:
      print '  Sample %5d / %d' % (i+1,n)

    if qnorm:
      x,y     = quantile_normalize(x,y,max_threshold=1.5)

    t         = (2/np.pi)*np.arctan2(y,x)

    r         = regress_intensity(x,y,design,dmask,genos,r_AA,r_AB,r_BB,rmodel=options.rmodel,thin=11)

    lrr,baf   = compute_lrr_baf(t,r,r_AA,r_AB,r_BB,t_AA,t_AB,t_BB)

    LRR_QN.write(lrr)
    BAF_QN.write(baf)

  # Close and flush re-normalize tables
  LRR_QN.close()
  BAF_QN.close()


if __name__ == '__main__':
  main()
