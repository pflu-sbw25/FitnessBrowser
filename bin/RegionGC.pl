#!/usr/bin/perl -w
# Compute GC content and #TA dinucleotides for each gene or region

use strict;

{
    die "usage: RegionGC.pl fna regions > regions_gc\n"
	. "   regions must include scaffold, begin, end, and strand fields\n"
	. "   begin and end must be 1-based and inclusive\n"
	. "   other fields are (silently) maintained\n"
	unless @ARGV == 2;
    my ($fnaFile, $regionsFile) = @ARGV;

    my %scaffoldIds = (); # which scaffolds we have seen
    my @header = (); # list of column names
    my @regions = (); # list of lists
    open(REGIONS, "<", $regionsFile) || die "Error reading $regionsFile";
    my ($iScaffold,$iBegin,$iEnd,$iStrand); # column numbers
    while(<REGIONS>) {
	chomp;
	my @F = split /\t/, $_, -1; # leave blank columns at end!
	if (@header == 0) {
            # header line
	    @header = @F;
	    my %header = map { $header[$_] => $_ } (0..(scalar(@header)-1));
	    $iScaffold = $header{"scaffold"};
	    $iScaffold = $header{"scaffoldId"} if !defined $iScaffold;
	    die "No scaffold or scaffoldId column" unless defined $iScaffold;
	    $iBegin = $header{"begin"};
	    die "No begin column" unless defined $iBegin;
	    $iEnd = $header{"end"};
	    die "No end column" unless defined $iEnd;
	    $iStrand = $header{"strand"};
	    die "No strand column" unless defined $iStrand;
	} else {
	    push @regions, [ $F[$iScaffold], $F[$iBegin], $F[$iEnd], $F[$iStrand], \@F ];
	    $scaffoldIds{$F[$iScaffold]} = 1;
	}
    }
    close(REGIONS) || die "Error reading $regionsFile";

    my %seqs = ();
    my $lastName = undef;
    open (FNA, "<", $fnaFile) || die "Error reading $fnaFile";
    while(<FNA>) {
	s/[\r\n]+$//;
	if (m/>(.*)$/) {
	    $lastName = $1;
	    $seqs{$lastName} = "";
	} else {
	    $seqs{$lastName} .= $_;
	}
    }
    close(FNA) || die "Error reading $fnaFile";


    # map scaffold in region file to the sequence name, which may be of the form name1|name2|name3 or somesuch
    my %scToSeqName = ();
    foreach my $seqName  (keys %seqs) {
	if (exists $scaffoldIds{$seqName}) {
	    $scToSeqName{$seqName} = $seqName;
	} else {
	    my @parts = split /[|]/, $seqName;
	    foreach my $part (@parts) {
		if ($part ne "" && exists $scaffoldIds{$part}) {
		    $scToSeqName{$part} = $seqName;
		}
	    }
	}
    }

    print join("\t", @header, "GC", "nTA")."\n";
    foreach my $region (@regions) {
	my ($scaffold,$begin,$end,$strand,$all) = @$region;
	my $seqName = $scToSeqName{$scaffold};
	die "No sequence for $scaffold" if !defined $seqName;
	my $seq = $seqs{$seqName};
	my $len = length($seq);
	die "Sequence for $seqName is too short: $end versus $len" if $end > $len;
	die "begin must be less than end: $begin $end" unless $begin < $end;
	my $subseq = substr($seq, $begin-1, $end-$begin+1);
	my $sublen = length($subseq);

	my @hits;
	@hits = $subseq =~ m/[GC]/g;
	my $nGC = scalar(@hits);
	@hits = $subseq =~ m/[AT]/g;
	my $nAT = scalar(@hits);
	die "No ACGT characters for $seqName $begin $end" if $nGC == 0 && $nAT == 0;

	my $trimmed = substr($subseq, int($sublen*0.1+0.5), int($sublen*0.8+0.5));
	@hits = $trimmed =~ m/TA/g;
	my $nTA = scalar(@hits);

	my $GC = sprintf("%.4f", $nGC / ($nGC+$nAT));
	print join("\t", @$all, $GC, $nTA)."\n";
    }
}
