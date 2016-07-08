#!/usr/bin/perl -w
use strict;
use Getopt::Long;
use FindBin qw($Bin);
use lib "$Bin/../lib";
use FEBA_Utils; # for ReadFasta()
use DBI;

my $gdir = "g";
my $reactionsfile = "metacyc_reactions.tab";
my $metaidsfile = "metacyc_ids.tab";
my $db = undef;
my $dir = ".";
my $minIdentity = 30;
my $minCoverage = 0.80;
my $maxLog10E = -2;
my $metaseqfile = "metacyc.faa";

my $usage = <<END
Usage: db_setup_metacyc.pl [ -db db_file_name ] [ -dir $dir ] org1 ... orgN

Given the output files from rap search (in
g/blast_results/metacyc_*.m8) and the metacyc ids and reactions files,
populates the MetaCyc-related tables. Will delete any existing data in
those tables, but the tables must already exist.

-dir specifies where the temporary files db.* will be stored.
(If there is no -db argument, the temporary files will not be removed.)

Other optional arguments, with defaults:
   -gdir $gdir -- the base directory
   -faa $metaseqfile -- the metacyc fasta file from ParseMetacycSeq.pl
   -ids $metaidsfile -- the metacyc fasta file from ParseMetacycSeqDat.pl
   -reactions $reactionsfile -- the output of ParseMetaCycReactions.pl
   -minIdentity $minIdentity -- minimum %identity
   -minCoverage $minCoverage -- minimum coverage both ways
END
    ;

die $usage unless GetOptions('db=s' => \$db,
                             'dir=s' => \$dir,
                             'reactions=s' => \$reactionsfile,
                             'gdir=s' => \$gdir,
                             'faa=s' => \$metaseqfile,
                             'minIdentity=f' => \$minIdentity,
                             'minCoverage=f' => \$minCoverage );
my @orgs = @ARGV;
die $usage unless scalar(@orgs) > 0;
die "No such directory: $dir" unless -d $dir;
die "No such directory: $gdir" unless -d $gdir;
die "No such directory: $gdir/blast_results" unless -d "$gdir/blast_results";
die "No such file: $reactionsfile" unless -e $reactionsfile;
die "No such file: $db" if defined $db && ! -e $db;
die "No such file: $metaseqfile" unless -e $metaseqfile;
die "No such file: $metaidsfile" unless -e $metaidsfile;

my $metaseqs = FEBA_Utils::ReadFasta($metaseqfile);

my %links = (); # sprotId => list of [ rxnId, ecNum ]
open(IDS, "<", $metaidsfile) || die "Cannot read $metaidsfile";
while(my $line = <IDS>) {
    chomp $line;
    my ($rxnId, $ecNum, $sprotId) = split "\t", $line;
    die "Cannot parse $line from $metaidsfile" unless defined $sprotId;
    push @{ $links{$sprotId} }, [ $rxnId, $ecNum ];
}

my $nGenes = 0;
open(OUT, ">", "$dir/db.BestHitMetacyc") || die "Cannot write to $dir/db.BestHitMetacyc";
foreach my $org (@orgs) {
    die "No such directory: $gdir/$org" unless -d "$gdir/$org";
    my $hitsfile = "$gdir/blast_results/metacyc_$org.m8";
    die "No such file: $hitsfile" unless -e $hitsfile;

    my $seqs = FEBA_Utils::ReadFasta("$gdir/$org/aaseq2");
    my %seen = ();

    open(HITS, "<", $hitsfile) || die "Cannot read $hitsfile";
    while(my $line = <HITS>) {
        chomp $line;
        next if $line =~ m/^#/; # comment lines in header
        my ($query,$subject,$identity,$alnlen,$mismatch,$gaps,$qstart,$qend,$sstart,$send,$log10E,$bits)
            = split /\t/, $line;
        die "Cannot parse\n$line\nfrom $hitsfile" unless defined $bits;
        die "No length for $query" unless exists $seqs->{$query};
        my $qlen = length( $seqs->{$query} );
        die "Invalid length for $query" if $qend > $qlen;
        die "No length for $subject" unless exists $metaseqs->{$subject};
        my $slen = length( $metaseqs->{$subject} );
        die "Invalid length for $subject" if $send > $slen;
        next unless ($qend-$qstart+1) >= $minCoverage * $qlen
            && ($send-$sstart+1) >= $minCoverage * $slen;
        next if exists $seen{$query};
        $seen{$query} = 1;
        next unless $identity >= $minIdentity && $log10E <= $maxLog10E;
        $nGenes++;
        my ($org2,$locusId) = split /:/, $query;
        die "Invalid query id $query" unless $org eq $org2 && defined $locusId && $locusId ne "";
        my $links = $links{$subject};
        die "No links for $subject the best hit of $query" unless defined $links;
        my %seenRxn = (); # prevent repeats of rxnIds
        foreach my $link (@$links) {
            my ($rxnId, $ecNum) = @$link;
            next if exists $seenRxn{$rxnId};
            $seenRxn{$rxnId} = 1;
            print OUT join("\t", $org, $locusId, $subject, $identity, $rxnId, $ecNum)."\n";
        }
    }
    close(HITS) || die "Error reading $hitsfile";
}
close(OUT) || die "Error writing to $dir/db.BestHitMetacyc";
print STDERR "Wrote hits for $nGenes genes to $dir/db.BestHitMetacyc\n";

if (defined $db) {
    open(SQLITE, "|-", "sqlite3", $db) || die "Cannot run sqlite3 on $db";
    print SQLITE ".mode tabs\n";
    foreach my $table (qw{BestHitMetacyc MetacycReaction}) {
        print SQLITE "DELETE from $table;\n";
    }
    print SQLITE ".import $dir/db.BestHitMetacyc BestHitMetacyc\n";
    print SQLITE ".import $reactionsfile MetacycReaction\n";
    close(SQLITE) || die "Error running sqlite3 on $db";
    print "Successfully loaded into $db -- deleting the db.* files\n";
    unlink("$dir/db.BestHitMetacyc");
}
