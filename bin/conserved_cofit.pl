#!/usr/bin/perl -w
# conserved_cofit.pl -- given an orthologs table and multiple fitness tables, identify
# pairs of genes & orthologs with conserved cofitness
use strict;
use Getopt::Long;

sub ReadOrthTable($);
sub ReadCofitFile($$$);

{
    my $usage = qq{
Usage: conserved_cofit.pl -orth ortholog_table -out prefix cofitfile1 ... cofitfileN > pairs

The ortholog table should contain locusId, taxonomyId, and
orthNNNN.locusId, where NNNN is the taxonomyId and orthologs in its
own genome are ignored.  The cofitness files (1 per organism) should
contain locusId, hitId, cofit, and rank. All input files
should be tab delimited with a header line.
};
    my $orthfile;
    my $out;
    (GetOptions('orth=s' => \$orthfile, 'out=s' => \$out)
     && defined $orthfile && defined $out) || die $usage;

    my @cofitfiles = @ARGV;
    die "No cofitness files" unless @cofitfiles > 0;

    # taxa: taxonomyId => locusId => 1
    # orth: locusId => taxonomyId => orthologId if it exists
    my ($taxa,$orth) = ReadOrthTable($orthfile);
    print STDERR "Read orthologs for " . scalar(keys %$orth) . " genes in ".scalar(keys %$taxa)." genomes\n";

    my %nTaxWithOrth = (); # for each taxon, the number of genes that have at least one ortholog
    foreach my $taxonomyId (sort keys %$taxa) {
	my $nWithOrth = 0;
	my $nGene = 0;
	foreach my $locusId (keys %{ $taxa->{$taxonomyId} }) {
	    $nGene++;
	    $nWithOrth++ if scalar(keys(%{ $orth->{$locusId} })) > 0;
	}
	print STDERR join("\t","nWithOrth",$taxonomyId,$nGene,$nWithOrth)."\n";
    }

    my %cofit = (); # taxon => locusId => hitId => [rank,cofitness]
    foreach my $cofitfile (@cofitfiles) {
	my ($taxonomyId, $cofit) = ReadCofitFile($cofitfile, $taxa, $orth);
	die "More than one cofitness file for $taxonomyId" if exists $cofit{$taxonomyId};
	$cofit{$taxonomyId} = $cofit;
    }
    foreach my $taxonomyId (sort keys %$taxa) {
	print STDERR "No cofitness file for $taxonomyId\n" unless exists $cofit{$taxonomyId};
    }
    print STDERR "Read " . scalar(keys %cofit) . " cofitness tables\n";

    # And find pairs that have hits both ways in two organisms
    # Orthologs are not necessarily bidirectional or transitive, so do not handle that aspect of it
    my $nFound = 0;
    open(OUT,">","$out.pairs") || die "Cannot write to $out.pairs";
    print OUT join("\t",qw{taxId locus1 locus2 rank cofit otax orth1 orth2 orank ocofit})."\n";

    foreach my $taxonomyId (sort keys %$taxa) {
	# gene1 => gene2 => taxon => 1 if there is conserved cofitness in that organism
	# only direction gene1 < gene2 is stored
	my %pairs = ();
	my @othertax = grep { $_ ne $taxonomyId } (keys %$taxa);
	while (my ($locus1, $hithash) = each %{ $cofit{$taxonomyId} }) {
	    while (my ($locus2, $hitrow) = each %$hithash) {
		next unless ($locus1 cmp $locus2) < 0;
		my ($rank1,$cofit1) = @$hitrow;
		next unless exists $cofit{$taxonomyId}{$locus2}{$locus1}; # must hit both ways
		my ($rank2,$cofit2) = @{ $cofit{$taxonomyId}{$locus2}{$locus1} };
		my $rank = $rank1 > $rank2 ? $rank1 : $rank2; # pessimistic estimate of importance
		die "cofitness for $locus1 $locus2 in taxon $taxonomyId is inconsistent: $cofit1 vs. $cofit2"
		    unless abs($cofit1 - $cofit2) <= 0.001;
		foreach my $othertax (@othertax) {
		    my $orth1 = $orth->{$locus1}{$othertax};
		    my $orth2 = $orth->{$locus2}{$othertax};
		    if (defined $orth1 && defined $orth2
			&& exists $cofit{$othertax}{$orth1}{$orth2} && exists $cofit{$othertax}{$orth2}{$orth1}) {
			$pairs{$locus1}{$locus2}{$othertax} = 1;
			$nFound++;
			my $orank1 = $cofit{$othertax}{$orth1}{$orth2}[0];
			my $orank2 = $cofit{$othertax}{$orth1}{$orth2}[0];
			my $orank = $orank1 > $orank2 ? $orank1 : $orank2;
			my $ocofit = $cofit{$othertax}{$orth1}{$orth2}[1];
			print OUT join("\t",$taxonomyId,$locus1,$locus2,$rank,$cofit1,
				       $othertax,$orth1,$orth2,$orank,$ocofit)."\n";
		    }
		}
	    }
	}
    }
    close(OUT) || die "Error writing to $out.pairs";
    print STDERR "Found $nFound cases of conserved cofitness (counting orthologs both ways)\n";
    print STDERR "Wrote $out.pairs\n";
}

# Returns references to taxa and orth hashes
sub ReadOrthTable($) {
    my ($orthfile) = @_;
    open(ORTH, "<", $orthfile) || die "Cannot read $orthfile";
    my $header = <ORTH>;
    chomp $header;
    my @colnames = split /\t/, $header;
    die "First column in ortholog table should be locus name" unless shift(@colnames) eq "locusId";
    die "Second column in ortholog table should be locus name" unless shift(@colnames) eq "taxonomyId";
    my @taxa = (); # in the order in the column names
    foreach my $name (@colnames) {
	$name =~ m/^orth(.*)[.][a-zA-z]+$/ || die "invalid ortholog field $name";
	push @taxa, $1;
    }
    # taxa: taxonomyId => locusId => 1
    my %taxa = map { $_ => {} } @taxa;
    die "Duplicate taxon names" if scalar(keys %taxa) != scalar(@taxa);
    # orth: 
    my %orth = ();
    while(my $line = <ORTH>) {
	chomp $line;
	my @F = split /\t/, $line, -1;
	die "Wrong number of fields in ortholog table:\n@F" unless scalar(@F) == scalar(@taxa)+2;
	my $locusId = shift @F;
	die "Duplicate entry for locus $locusId" if exists $orth{$locusId};
	$orth{$locusId} = {}; # so we know it is a valid locusId
	my $taxonomyId = shift @F;
	$taxa{$taxonomyId}{$locusId} = 1;
	die "Invalid taxonomy $taxonomyId in ortholog table" unless exists $taxa{$taxonomyId};
	foreach my $orthtax (@taxa) {
	    my $orthId = shift @F;
	    die $line if !defined $orthId;
	    $orth{$locusId}{$orthtax} = $orthId if $orthId ne "" && $orthtax ne $taxonomyId;
	}
    }
    close(ORTH) || die "Error reading $orthfile";
    return(\%taxa, \%orth);
}

# returns taxonomyId and a hash of locusId => hitId => [rank,cofitness]
sub ReadCofitFile($$$) {
    my ($cofitfile,$taxa,$orth) = @_;
    open(COFIT, "<", $cofitfile) || die "Cannot read $cofitfile";
    my $header = <COFIT>;
    chomp $header;
    my @colnames = split /\t/, $header;
    die "Invalid cofitness file $cofitfile" unless @colnames >= 4
	&& $colnames[0] eq "locusId"
	&& uc($colnames[3]) eq uc("rank");

    my %cofit = (); # locusId => hitId => [rank,cofitness]
    my %skip = (); # locusIds not in keys of %$orth
    while(my $line = <COFIT>) {
	chomp $line;
	my @F = split /\t/, $line;
	die "Error reading cofitness file $cofitfile:\n$line\nhas wrong number of columns"
	    unless scalar(@F) == scalar(@colnames);
	my ($locusId,$hitId,$cor,$rank) = @F;
	if (!exists $orth->{$locusId}) {
	    $skip{$locusId} = 1;
	} else {
	    die "Invalid cofitness line $line" unless $rank =~ m/^\d+$/;
	    die "Duplicate hit $hitId for $locusId" if exists $cofit{$locusId}{$hitId};
	    if (exists $orth->{$hitId}) {
		$cofit{$locusId}{$hitId} = [ $rank, $cor ];
	    }
	}
    }
    # and check what taxon we are in
    die "No known loci in $cofitfile" unless scalar(keys %cofit) > 0;
    my $locus1 = (keys %cofit)[0];
    my @taxonomyIds = grep { exists $taxa->{$_}{$locus1} } (keys %$taxa);
    my $taxonomyId = $taxonomyIds[0];
    foreach my $locusId (keys %cofit) {
	die "locus $locusId in $cofitfile is not in taxonomyId $taxonomyId"
	    unless exists $taxa->{$taxonomyId}{$locusId};
    }
    print STDERR "Skipping loci for taxon $taxonomyId in $cofitfile: " . join(" ",sort keys %skip) . "\n"
	if scalar(keys %skip) > 0;
    return($taxonomyId,\%cofit);
}
