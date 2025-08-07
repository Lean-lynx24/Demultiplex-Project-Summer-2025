from __future__ import print_function
import os
import re
import gzip
import itertools
import argparse
import time
import logging

logger = logging.getLogger('root')

def fq(file):
    """A generator to read a FASTQ file (gzipped or not) and yield records one by one."""
    if re.search('.gz$', file):
        fastq = gzip.open(file, 'rb')
    else:
        fastq = open(file, 'r')
    with fastq as f:
        while True:
            l1 = f.readline()
            if not l1:
                break
            # In Python 3, gzipped files are read in bytes, so decode to string
            if isinstance(l1, bytes):
                l1 = l1.decode('utf-8')
                l2 = f.readline().decode('utf-8')
                l3 = f.readline().decode('utf-8')
                l4 = f.readline().decode('utf-8')
            else:
                l2 = f.readline()
                l3 = f.readline()
                l4 = f.readline()
            yield [l1, l2, l3, l4]

def get_sample_id(r1, sample_names):
    """
    Extracts the barcode from the Read 1 header and returns a sample ID.
    Assumes Illumina format: @... 1:N:0:BARCODE1+BARCODE2
    """
    header = r1[0].strip()
    try:
        # The barcode info is the last part of the header, e.g., '1:N:0:CATGGC+ATGCAT'
        barcode_info = header.split(' ')[-1]
        # The barcode itself is the last part of that, after the final colon
        full_barcode = barcode_info.split(':')[-1]

        # The original script expected a concatenated 16-base barcode (8 from each index).
        # We will replicate that logic here by splitting the barcode from the header.
        if '+' in full_barcode:
            index1, index2 = full_barcode.split('+')
            sample_barcode = index1[:8] + index2[:8]
        else:
            # If there's no '+', assume the barcode is already in the correct format
            sample_barcode = full_barcode

    except (IndexError, ValueError):
        # If the header format is unexpected, we can't determine the barcode
        return 'unknown_barcode_format'

    # Return the friendly sample name if it exists, otherwise return the barcode itself
    return sample_names.get(sample_barcode, sample_barcode)


def demultiplex(read1, read2, sample_barcodes, out_dir, min_reads=10):
    """
    Demultiplexes reads based on barcodes found in the read headers.
    """
    if not os.path.exists(out_dir):
        os.makedirs(out_dir)

    # Load sample names from barcode file
    sample_names = {}
    if sample_barcodes and os.path.exists(sample_barcodes):
        with open(sample_barcodes, 'r') as f:
            for line in f:
                fields = line.strip().split() # Split by tab or space
                if len(fields) == 2:
                    sampleid, barcode = fields
                    sample_names[barcode] = sampleid

    outfiles_r1 = {}
    outfiles_r2 = {}
    count = {}
    buffer_r1 = {}
    buffer_r2 = {}

    total_count = 0
    start = time.time()

    # Process reads in pairs from Read 1 and Read 2 files
    for r1, r2 in itertools.izip(fq(read1), fq(read2)):
        total_count += 1
        if total_count % 1000000 == 0:
            logger.info("Processed %d reads in %.1f minutes.", total_count, (time.time() - start) / 60)
        
        # Get sample ID from the Read 1 header
        sample_id = get_sample_id(r1, sample_names)

        # Initialize counter and buffer for new samples
        if sample_id not in count:
            count[sample_id] = 0
            buffer_r1[sample_id] = []
            buffer_r2[sample_id] = []
        count[sample_id] += 1

        # Buffer reads until min_reads threshold is met
        if count[sample_id] < min_reads:
            buffer_r1[sample_id].append(r1)
            buffer_r2[sample_id].append(r2)
        # When threshold is met, open files and write the buffered reads
        elif count[sample_id] == min_reads:
            outfiles_r1[sample_id] = open(os.path.join(out_dir, '%s.r1.fastq' % sample_id), 'w')
            outfiles_r2[sample_id] = open(os.path.join(out_dir, '%s.r2.fastq' % sample_id), 'w')

            # Write buffered reads
            for record in buffer_r1[sample_id]:
                outfiles_r1[sample_id].write(''.join(record))
            for record in buffer_r2[sample_id]:
                outfiles_r2[sample_id].write(''.join(record))
            
            # Write the current read
            outfiles_r1[sample_id].write(''.join(r1))
            outfiles_r2[sample_id].write(''.join(r2))

            # Clear the buffer to save memory
            del buffer_r1[sample_id]
            del buffer_r2[sample_id]
        # For reads beyond the threshold, write directly to the file
        else:
            outfiles_r1[sample_id].write(''.join(r1))
            outfiles_r2[sample_id].write(''.join(r2))

    # Write remaining buffered reads (from samples with < min_reads) to undetermined files
    undetermined_r1 = open(os.path.join(out_dir, 'undetermined.r1.fastq'), 'w')
    undetermined_r2 = open(os.path.join(out_dir, 'undetermined.r2.fastq'), 'w')
    for sample_id in buffer_r1:
        for record in buffer_r1[sample_id]:
            undetermined_r1.write(''.join(record))
        for record in buffer_r2[sample_id]:
            undetermined_r2.write(''.join(record))

    # Close all opened files
    for sample_id in outfiles_r1:
        outfiles_r1[sample_id].close()
        outfiles_r2[sample_id].close()
    undetermined_r1.close()
    undetermined_r2.close()

    num_fastqs = len([v for k, v in count.items() if v >= min_reads])
    logger.info('Wrote FASTQs for %d sample barcodes (out of %d total) with at least %d reads.', num_fastqs, len(count), min_reads)

def main():
    parser = argparse.ArgumentParser(description="Demultiplex FASTQ files based on barcodes in the read headers.")
    parser.add_argument('--read1', required=True, help="Path to the R1 FASTQ file.")
    parser.add_argument('--read2', required=True, help="Path to the R2 FASTQ file.")
    parser.add_argument('--sample_barcodes', required=True, help="Path to a tab-separated file mapping sample_name to barcode.")
    parser.add_argument('--out_dir', default='demux_output', help="Directory to write output FASTQ files.")
    parser.add_argument('--min_reads', type=int, default=10, help="Minimum number of reads to create a sample-specific FASTQ file.")
    args = vars(parser.parse_args())

    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
    
    demultiplex(args['read1'], args['read2'], args['sample_barcodes'], args['out_dir'], min_reads=args['min_reads'])

if __name__ == '__main__':
    main()
