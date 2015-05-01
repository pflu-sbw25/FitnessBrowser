#!/usr/bin/perl -w
#######################################################
## myFitShow.cgi
##
## Copyright (c) 2015 University of California
##
## Authors:
## Wenjun Shao (wjshao@berkeley.edu) and Morgan Price
#######################################################
#
# Required CGI parameters:
# gene -- a locusId, sysName, or gene name to match on
#	(may show multiple hits)
# Optional CGI parameters:
# orgId -- which organism to search in
# showAll -- 1 if showing all fitness values instead of just the most extreme ones

use strict;

use CGI qw(:standard Vars);
use CGI::Carp qw(warningsToBrowser fatalsToBrowser);
use DBI;

use lib "../lib";
use Utils;

my $cgi=CGI->new;
my $style = Utils::get_style();

# read the input information

my $orgSpec = $cgi->param('orgId') || "";
my $geneSpec = $cgi->param('gene') || die "no gene name found\n";
my $showAll = $cgi->param('showAll') ? 1 : 0;

$geneSpec =~ s/ *$//;
$geneSpec =~ s/^ *//;

print $cgi->header;
print $cgi->start_html(
    -title =>"Fitness",
    -style => {-code => $style},
    -author=>'wjshaoATberkeley.edu',
    -meta=>{'copyright'=>'copyright 2015 UC Berkeley'},
);

# check user input

Utils::fail($cgi, "$geneSpec is invalid. Please enter correct gene name!") unless ($geneSpec =~ m/^[A-Za-z0-9_-]*$/);

# connect to database

my $dbh = Utils::get_dbh();
my $orginfo = Utils::orginfo($dbh);

my $query = qq{SELECT orgId, locusId, sysName, desc, gene FROM Gene
		WHERE ( locusId = ? OR sysName = ? OR upper(gene) = upper(?) )};
my $hits;
if ($orgSpec) {
    $query .= " AND orgId = ?";
    $hits = $dbh->selectall_arrayref($query, { Slice => {} }, $geneSpec, $geneSpec, $geneSpec, $orgSpec);
} else {
    $hits = $dbh->selectall_arrayref($query, { Slice => {} }, $geneSpec, $geneSpec, $geneSpec);
}

# and add another column for whether there is fitness data
foreach my $gene (@$hits) {
    $gene->{has_fitness} = Utils::gene_has_fitness($dbh,$gene->{orgId},$gene->{locusId});
}

if (@$hits == 0) {
    print $cgi->h3("No gene found for $geneSpec");
} elsif (@$hits > 1) {
    print $cgi->h3("Genes found for $geneSpec:");
    my @trows = ();
    push @trows, $cgi->Tr({-align=>'CENTER',-valign=>'TOP'},
			  $cgi->th( [ 'geneId','sysName','geneName','description','genome','fitness' ] ) );
    foreach my $gene (@$hits) {
	my $fitString = $cgi->a( { href => "myFitShow.cgi?orgId=$gene->{orgId}&gene=$gene->{locusId}", },
				   $gene->{has_fitness} ? "has data" : "no data" );
	my @trow = map $cgi->td($_), ($gene->{locusId}, $gene->{sysName}, $gene->{gene}, $gene->{desc},
				      $orginfo->{$gene->{orgId}}->{genome}, $fitString );
	push @trows, $cgi->Tr(@trow);
    }
    
    print $cgi->table( { cellspacing=>0, cellpadding=>3 }, @trows);
    
} else {
    # just 1 hit
    my $gene = $hits->[0];
    my $orgId = $gene->{orgId};
    my $locusId = $gene->{locusId};

    if ($hits->[0]{has_fitness} == 0) {
	my $idShow = $gene->{sysName} || $gene->{locusId};
	print $cgi->h3("$idShow $gene->{gene}: $gene->{desc} in " . $orginfo->{$gene->{orgId}}{genome});
	print $cgi->p("Sorry, no fitness data for $idShow");
    } else {
	# show fitness data for gene
	my @fit = @{ $dbh->selectall_arrayref("SELECT expName,fit,t from GeneFitness where orgId=? AND locusId=?",
					      { Slice => {} },
					      $orgId, $locusId) };
	my $nTotValues = scalar(@fit);
	die "Unreachable" if $nTotValues == 0;
	my $limitRows = $showAll ? $nTotValues : 20;
	my $minAbsFit;
	if ($nTotValues > $limitRows) {
	    # subset the rows
	    @fit = sort { abs($b->{fit}) <=> abs($a->{fit}) } @fit;
	    @fit = @fit[0..($limitRows-1)];
	    $minAbsFit = abs($fit[$#fit]{fit});
	}

	# and get metadata about experiments
	my $expinfo = Utils::expinfo($dbh,$orgId);

	if ($showAll) {
	    @fit = sort { Utils::CompareExperiments($expinfo->{$a->{expName}}, $expinfo->{$b->{expName}}) } @fit;
	} else {
	    @fit = sort { $a->{fit} <=> $b->{fit} } @fit;
	}

	my $idShow = $gene->{sysName} || $gene->{locusId};
	print $cgi->h2("Fitness data for gene $idShow in $orginfo->{$orgId}{genome}");
	print $cgi->h3("$idShow $gene->{gene}: $gene->{desc}");
	if ($showAll) {
	    print $cgi->p("All " . scalar(@fit) . " fitness values, sorted by group and condition");
	} else {
	    if (defined $minAbsFit) {
		$minAbsFit = sprintf("%.1f", $minAbsFit);
		print $cgi->p("Top $limitRows experiments with the strongest phenotypes (|fitness| &ge; $minAbsFit)");
	    } else {
		print $cgi->p("All " . scalar(@fit) . " fitness values, sorted by value");
	    }
	}
	    
	my @out = (); # specifiers for HTML rows for each fitness value
	my $lastGroup = ""; # only enter the first time
	foreach my $fitrow (@fit) {
	    my $expName = $fitrow->{expName};
	    my $exp = $expinfo->{$expName};
	    my $group = $exp->{expGroup};
	    push @out, join(" ",
			    td($group eq $lastGroup ? "" : $group),
			    td(a({ style => "color:rgb(0,0,0)",
					       title => "$expName: $exp->{expDescLong}",
					       href => "exp.cgi?orgId=$orgId&expName=$expName" },
					       $exp->{expDesc})),
			    td( { -bgcolor => Utils::fitcolor($fitrow->{fit}) },
				      sprintf("%.1f", $fitrow->{fit}) ),
			    td( sprintf("%.1f", $fitrow->{t}) ),
			    td(a({ style => "color:rgb(0,0,0)",
				   title => "Compare to data from similar experiments or orthologs",
				   href => "orthFit.cgi?orgId=$orgId&locusId=$locusId&expGroup=$exp->{expGroup}&condition1=$exp->{condition_1}" }),
				 "compare") );
	    $lastGroup = $group if $showAll;
	}
	my $relsize = $showAll ? "70%" : "100%";
	print $cgi->table(
	    { cellspacing => 0, cellpadding => 3, },
	    $cgi->Tr({-align=>'CENTER',-valign=>'TOP'},
		     $cgi->th( [ 'group', 'condition','fitness','t score', '&nbsp;' ] ) ),
            $cgi->Tr({-align=>'left',-valign=>'top',-style=>"font-size: $relsize"}, \@out ) );

	# Option to add a gene (links to genesFit.cgi)
	print $cgi->start_form(-name => 'input', -method => 'GET', -action => 'genesFit.cgi');
	print "<P>Add gene: ";
	print $cgi->hidden( 'orgId', $orgId );
	print $cgi->hidden( 'showAll', $showAll );
	print qq{<input type="hidden" name="locusId" value="$locusId" />\n};
	print $cgi->textfield( -name => 'addgene', -default => "", -override => 1, -size => 20, -maxLength => 100 );
	print $cgi->end_form;

	# links
	if ($showAll == 0) {
	    my $showAllDest = qq(myFitShow.cgi?orgId=$orgId&gene=$locusId&showAll=1);
	    print $cgi->p(qq(<a href=$showAllDest>All fitness data</a>));
	} else {
	    my $showFewDest = qq(myFitShow.cgi?orgId=$orgId&gene=$locusId&showAll=0);
	    print $cgi->p(qq(<a href=$showFewDest>Strongest phenotypes</a>));
	}
	print $cgi->p($cgi->a( { href => "genesFit.cgi?orgId=$orgId&locusId=$locusId&around=2" }, "Fitness for nearby genes"));
	print $cgi->p($cgi->a({href => "cofit.cgi?orgId=$orgId&locusId=$locusId"}, "Top cofit genes"));
    } # end else unique hit has data

    my @links = ();
    if ($gene->{locusId} =~ m/^\d+$/) {
	push @links, $cgi->a({href => "http://www.microbesonline.org/cgi-bin/fetchLocus.cgi?locus=$gene->{locusId}"},
			     "MicrobesOnline");
    }
    if ($orgId eq "Keio" && $gene->{sysName} =~ m/^b\d+$/) {
	push @links, $cgi->a({href => "http://ecocyc.org/ECOLI/search-query?type=GENE&gname=$gene->{sysName}"}, "EcoCyc");
    }
    print $cgi->p("Links: " . join(", ", @links)) if (@links > 0);

    # check homologs where or not gene has data
    my $dest = qq(mySeqSearch.cgi?orgId=$orgId&locusId=$locusId);
    print $cgi->p(qq(<a href=$dest>Check homologs</a>));

} #  end if just 1 hit

$dbh->disconnect();
Utils::endHtml($cgi);
