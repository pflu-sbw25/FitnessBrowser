#
#######################################################
## Utils.pm -- helper functions for the FEBA cgi code
##
## Copyright (c) 2015 All Right Reserved by UC Berkeley
##
## Authors:
## Wenjun Shao (wjshao@berkeley.edu) and Morgan Price
#######################################################

package Utils;
require Exporter;

use strict;
use warnings;

use DBI;
use Time::HiRes;
use Carp;

sub start_page($);
sub get_style();
sub tabsGene($$$$$$$);
sub tabsExp($$$$$$$);
sub fail($$);
sub formatFASTA($$);
sub crc64($);
sub fitcolor($);
sub get_dbh(); # open the sqlite db and return the resulting database handle
sub blast_db();
sub tmp_dir();
sub orginfo($);
sub get_orths($$$);

#--------------------------------------------------------

sub start_page($) {
    my ($title) = @_;
    my $url = CGI::url();
    my $public = $url =~ m/fit.genomics/;
    my $site_name = $public  ? "Fitness Browser" : "Private Fitness";
    my $color = $public ? "gold" : "white";
    my $header = <<"EOT";

    <!DOCTYPE html>
    <html xmlns="http://www.w3.org/1999/xhtml" lang="en-US" xml:lang="en-US">
    <head>
    <meta http-equiv="X-UA-Compatible" content="IE=edge"> 
    <link rev="made" href="mailto:morgannprice%40yahoo.com" />
    <title>$title</title>
    <meta name="copyright" content="copyright 2015 UC Berkeley" />
    <link rel="shortcut icon" href="../images/favicon.ico" type="image/x-icon">
    <link rel="icon" href="../images/favicon.ico" type="image/x-icon">
    <link rel="stylesheet" href="../images/feba2.css">
    <link href='http://fonts.googleapis.com/css?family=Montserrat:700' rel='stylesheet' type='text/css'>
    <meta http-equiv="Content-Type" content="text/html; charset=iso-8859-1" />
        </head>
    <body>
    <div id="page">
    <div id="nav"> <div class="box">
        <li class="header"><A style="color: $color;" TITLE="$site_name: fitness data from the Deutschbauer lab, the Arkin lab, and collaborators" HREF="myFrontPage.cgi">$site_name</A></li>
        <li><a href="myFrontPage.cgi">Home</a></li>
        <li><a href="geneSearch.cgi">Find Gene</a></li>
        <li><a href="blastSearch.cgi">BLAST</a></li>
        <li><a href="expSearch.cgi">Experiments</a></li>
        <li><a href="orgAll.cgi">Organisms</a></li>
        <li><a href="help.cgi">Help</a></li>
        </div></div>
      
    <div id="main">
EOT
    return $header;
}

sub get_style() {
    my $style = <<"EOT";
    body {
        font-family: verdana, arial, sans-serif;
    }
    H2 {
        color: red;
        /*border-bottom: 1pt solid;*/
    }
    H4 {
        color: blue;
    }
    table {
        border: black thin solid;
    }
    th,td {
        border: lightgrey thin solid;
    }

.axis path,
.axis line {
  fill: none;
  stroke: #000;
  shape-rendering: crispEdges;
}

.dot {
  stroke: none;
}

.line {
  position: relative;
  margin: 0 auto;
  height: 7px;
  z-index: 0;
  margin-top: 5px;
  margin-bottom: 0 auto;
  padding-left: 10px;
  padding-right: 10px;
}

.line2 {
  position: absolute;
  top: 0px;
  height: 7px;
  z-index: 2;
}

EOT
    return $style;
}

# Print a failure notice and then exit.
# Prints the HTML header (<HTML><TITLE> etc.) but *not* the CGI header
sub fail($$) {
    my ($cgi, $notice) = @_;
    print Utils::start_page("Sorry!");
    print '<div id="ntcontent">',
    $cgi->h3(qq(Sorry: $notice)),
    $cgi->h4(qq(<a href="javascript:history.back()">Go Back</a>)),
    $cgi->h4(qq(<a href="myFrontPage.cgi">Go to Front Page</a>));
    print $cgi->end_html;
    exit;
}

sub endHtml($) {
    my ($cgi) = @_;
    # print $cgi->p(qq(<a href="myFrontPage.cgi">Go back to front page</a>));
    print $cgi->end_html;
    exit 0;
}

#--------------------------------------------------------

sub formatFASTA($$)
{
    my ($title, $sequence) = @_;
    return undef unless ($sequence);
    my $s = qq/>$title\n/;
    my @whole = $sequence =~ /.{1,60}/g;
    my $line = join "\n", @whole;
    return $s."$line\n";
}

#--------------------------------------------------------

# color code fitness value in range (-3 .. 0 .. 3) to blue => white => yellow
sub fitcolor($) {
    my ($fit) = @_;
    return " #BFBFBF" if !defined $fit;
    my $perc = ($fit + 3)/6;
    $perc = $perc > 1 ? 1 : $perc;
    $perc = $perc < 0 ? 0 : $perc;
    return fractioncolor($perc);
}

# from a fraction 0:1 to a color
sub fractioncolor($) {
#RED (255, 0, 0)
#YELLOW (255, 255, 0)
#BLUE (0, 0, 255)
#WHITE (255, 255, 255)

    my ($perc) = shift @_;
    my ($red, $blue, $green);

# I need "BLUE-WHITE-YELLOW" scheme
    if($perc >= 0.5) {
        $red = 255;
        $green = $red;
        $blue = int(255 * 2 * (1 - $perc) + 0.5);
    } else {
        $red = int(($perc/0.5)*255 + 0.5);
        $green = $red;
        $blue = 255;
    }

    my $string=sprintf ("#%2.2X%2.2X%2.2X",$red,$green,$blue);
    return ($string);
}

sub get_dbh() {
    my $database = "../cgi_data/feba.db";
    return DBI->connect("dbi:SQLite:dbname=$database","","",{ RaiseError => 1 }) || die $DBI::errstr;
}

sub blast_db() {
    return "../cgi_data/aaseqs";
}

sub tmp_dir() {
    return "../tmp";
}

####
sub gene_has_fitness($$$) {
    my ($dbh,$orgId,$locusId) = @_;
    die unless defined $dbh && $orgId && defined $locusId;
    my @result = $dbh->selectrow_array("SELECT expName FROM GeneFitness WHERE orgId=? AND locusId=? LIMIT 1",
				       undef, $orgId, $locusId);
    return scalar(@result) > 0 ? 1 : 0;
}

sub gene_has_cofitness($$$) {
    my ($dbh,$orgId,$locusId) = @_;
    die unless defined $dbh && $orgId && defined $locusId;
    my @result = $dbh->selectrow_array("SELECT cofit FROM Cofit WHERE orgId=? AND locusId=? LIMIT 1",
                       undef, $orgId, $locusId);
    return scalar(@result) > 0 ? 1 : 0;
}

# returns a hash of orgId => attribute => value, including "genome" for the display name
sub orginfo($) {
    my ($dbh) = @_;
    my $orginfo = $dbh->selectall_hashref("SELECT * FROM Organism", "orgId");
    while (my ($orgId,$row) = each %$orginfo) {
	$row->{genome} = join(" ", $row->{genus}, $row->{species}, $row->{strain});
    }
    return $orginfo;
}

# returns a hash of expName => attribute => value
sub expinfo($$) {
    my ($dbh,$orgId) = @_;
    return $dbh->selectall_hashref("SELECT * FROM Experiment WHERE orgId = ?", "expName", {}, $orgId);
}

# Like cmp but for experiments, for ordering by group and condition/concentration, with
# expDesc as a fallback.
# Each argument should be a hash corresponding to a row in the Experiment table
sub CompareExperiments($$) {
    my ($expA,$expB) = @_;
    die unless defined $expA->{expGroup} && defined $expB->{expGroup};
    return $expA->{expGroup} cmp $expB->{expGroup}
           || lc($expA->{condition_1}) cmp lc($expB->{condition_1})
           || $expA->{concentration_1} cmp $expB->{concentration_1}
           || lc($expA->{expDesc}) cmp lc($expB->{expDesc});
}

# Should check that orgId is valid (if it is not empty) before calling.
# Allows partial-word matches in Condition_1 or Condition_2, or full word matches to expDesc or expDescLong, or exact match to Group.
# Note is not case sensitive
sub matching_exps($$$) {
    my ($dbh,$orgId,$expSpec) = @_;
    die if !defined $dbh || !defined $orgId || !defined $expSpec;
    # make the query safe to include in SQL
    $expSpec =~ s/^ +//;
    $expSpec =~ s/ +$//;
    $expSpec =~ s/[\"\n\r]//g;

    my $orgClause = $orgId eq "" ? "" : qq{ AND orgId = "$orgId"};
    my $sql = qq{SELECT * from Organism JOIN Experiment USING (orgId)
             WHERE (expName = "$expSpec"
	            OR Condition_1 LIKE "$expSpec%" OR Condition_1 LIKE "% $expSpec%"  OR Condition_1 LIKE "%-$expSpec%"
		    OR Condition_2 LIKE "$expSpec%" OR Condition_2 LIKE "% $expSpec%"  OR Condition_2 LIKE "%-$expSpec%"
	     	    OR expGroup = '$expSpec'
	            OR expDesc = '$expSpec' OR expDesc LIKE "$expSpec %" OR expDesc LIKE "% $expSpec" OR expDesc LIKE "% $expSpec %"
	            OR expDescLong = '$expSpec' OR expDescLong LIKE "$expSpec %" OR expDescLong LIKE "% $expSpec" OR expDescLong LIKE "% $expSpec %")
	     $orgClause
	     ORDER BY genus, species, strain, expGroup, condition_1, concentration_1, expDesc;};
         # die $sql;
    return $dbh->selectall_arrayref($sql, { Slice => {} });
}

sub matching_genes($$$) {
    my ($dbh,$orgId,$geneSpec) = @_;
    die if !defined $dbh || !defined $orgId || !defined $geneSpec;
    # make the query safe to include in SQL
    $geneSpec =~ s/^ +//;
    $geneSpec =~ s/ +$//;
    $geneSpec =~ s/[\"\n\r]//g;

    my $orgClause = $orgId eq "" ? "" : qq{ AND orgId = "$orgId"};
    my $sql = qq{SELECT * from Organism JOIN Gene USING (orgId)
             WHERE (
                sysName = "$geneSpec" OR sysName LIKE "$geneSpec"
                OR gene = "$geneSpec" OR gene LIKE "$geneSpec"
                OR locusId = "$geneSpec"
                OR desc LIKE "% $geneSpec" OR desc LIKE "$geneSpec %" OR desc LIKE "% $geneSpec %")                
         $orgClause
         ORDER BY genus, species, strain, locusId, sysName, gene, begin, end, desc;};
         # die $sql;
    return $dbh->selectall_arrayref($sql, { Slice => {} });
}

sub matching_exact($$$) {
    my ($dbh,$orgId,$geneSpec) = @_;
    die if !defined $dbh || !defined $orgId || !defined $geneSpec;
    # make the query safe to include in SQL, remove leading/trailing space
    $geneSpec =~ s/^ +$//;
    $geneSpec =~ s/ +$//;
    $geneSpec =~ s/[\"\n\r]//g;

    my $orgClause = $orgId eq "" ? "" : qq{ AND orgId = "$orgId"};
    my $sql = qq{SELECT * from Organism JOIN Gene USING (orgId)
             WHERE (
                sysName = "$geneSpec" OR sysName LIKE "$geneSpec"
                OR gene = "$geneSpec" OR gene LIKE "$geneSpec"
                OR locusId = "$geneSpec")             
         $orgClause
         ORDER BY genus, species, strain, locusId, sysName, gene, begin, end, desc
         LIMIT 100;};
         # die $sql;
    return $dbh->selectall_arrayref($sql, { Slice => {} });
}

# Matching against words in the reannotation or the description was originally
# implemented with a series of LIKE statements:
# new_annotation = "$geneSpec"
# OR new_annotation LIKE "% $geneSpec" OR new_annotation LIKE "$geneSpec %" OR new_annotation LIKE "% $geneSpec %"
# OR new_annotation LIKE "$geneSpec-%" OR new_annotation LIKE "$geneSpec-"
# OR new_annotation LIKE "% $geneSpec-%" OR new_annotation LIKE "%-$geneSpec %"
# OR new_annotation LIKE "$geneSpec/%" OR new_annotation LIKE "%/$geneSpec"
# OR new_annotation LIKE "% $geneSpec/%" OR new_annotation LIKE "%/$geneSpec %"
# OR new_annotation LIKE "$geneSpec,%" OR new_annotation LIKE "% $geneSpec,%"
# OR new_annotation LIKE "%-$geneSpec,%"
# but this can be stated more succinctly with sqlite3's GLOB operator.
# Because GLOB is case specific, need to lowercase both the query and the description.

sub matching_reanno($$$) {
    my ($dbh,$orgId,$geneSpec) = @_;
    die if !defined $dbh || !defined $orgId || !defined $geneSpec;
    # make the query safe to include in SQL
    $geneSpec =~ s/^ +//;
    $geneSpec =~ s/ +$//;
    $geneSpec =~ s/[\"\n\r]//g;
    $geneSpec = lc($geneSpec);
    my $exact = $geneSpec;
    # replace GLOB special characters with ?, which matches any one character
    $geneSpec =~ s/[*\[\]]/?/g;

    my $orgClause = $orgId eq "" ? "" : qq{ AND orgId = "$orgId"};
    my $wordend = "[ /,;()-]";
    my $sql = qq{SELECT * from Organism JOIN Gene USING (orgId) JOIN Reannotation USING (orgId,locusId)
                 WHERE
                 ( lower(new_annotation) = "$exact"
                   OR lower(new_annotation) GLOB "$geneSpec$wordend*"
                   OR lower(new_annotation) GLOB "*$wordend$geneSpec$wordend*"
                   OR lower(new_annotation) GLOB "*$wordend$geneSpec" )
                 $orgClause
                 ORDER BY genus, species, strain, locusId, sysName, gene, begin, end, new_annotation
                 LIMIT 100;};
    return $dbh->selectall_arrayref($sql, { Slice => {} });
}

sub matching_descs($$$) {
    my ($dbh,$orgId,$geneSpec) = @_;
    die if !defined $dbh || !defined $orgId || !defined $geneSpec;
    # make the query safe to include in SQL
    $geneSpec =~ s/^ +//;
    $geneSpec =~ s/ +$//;
    $geneSpec =~ s/[\"\n\r]//g;
    $geneSpec = lc($geneSpec);
    my $exact = $geneSpec;
    # replace GLOB special characters with ?, which matches any one character
    $geneSpec =~ s/[*\[\]]/?/g;

    my $orgClause = $orgId eq "" ? "" : qq{ AND orgId = "$orgId"};
    my $wordend = "[ /,;()-]";
    my $sql = qq{SELECT * from Organism JOIN Gene USING (orgId)
                 WHERE
                 ( lower(desc) = "$exact"
                   OR lower(desc) GLOB "$geneSpec$wordend*"
                   OR lower(desc) GLOB "*$wordend$geneSpec$wordend*"
                   OR lower(desc) GLOB "*$wordend$geneSpec" )
                 $orgClause
                 ORDER BY genus, species, strain, locusId, sysName, gene, begin, end, desc
                 LIMIT 100;};
    return $dbh->selectall_arrayref($sql, { Slice => {} });
}

sub matching_seed_descs($$$) {
    my ($dbh,$orgId,$geneSpec) = @_;
    die if !defined $dbh || !defined $orgId || !defined $geneSpec;
    # make the query safe to include in SQL
    $geneSpec =~ s/^ +//;
    $geneSpec =~ s/ +$//;
    $geneSpec =~ s/[\"\n\r]//g;

    my $orgClause = $orgId eq "" ? "" : qq{ AND orgId = "$orgId"};
    my $sql = qq{SELECT * FROM SeedAnnotation JOIN Gene USING (orgId,locusId) JOIN Organism USING (orgId)
             WHERE (
                seed_desc = "$geneSpec"
                OR seed_desc LIKE "% $geneSpec" OR seed_desc LIKE "$geneSpec %" OR seed_desc LIKE "% $geneSpec %"
                OR seed_desc LIKE "$geneSpec-%" OR seed_desc LIKE "$geneSpec-"
                OR seed_desc LIKE "% $geneSpec-%" OR seed_desc LIKE "%-$geneSpec %"
                OR seed_desc LIKE "$geneSpec/%" OR seed_desc LIKE "%/$geneSpec"
                OR seed_desc LIKE "% $geneSpec/%" OR seed_desc LIKE "%/$geneSpec %"
                OR seed_desc LIKE "$geneSpec,%" OR seed_desc LIKE "% $geneSpec,%"
                )
         $orgClause
         ORDER BY genus, species, strain, locusId, sysName, gene, begin, end, seed_desc 
         LIMIT 100;};
    return $dbh->selectall_arrayref($sql, { Slice => {} });
}

# third argument is an arrayref of KEGG ortholog groups, i.e. K14333
sub matching_kgroup($$$) {
    my ($dbh,$orgId,$kgroups) = @_;
    return [] if @$kgroups == 0;
    my $kgroupSpec = join(",", map {"'".$_."'"} @$kgroups);
    my $orgClause = $orgId eq "" ? "" : qq{ AND orgId = "$orgId"};
    my $sql = qq{SELECT * from Organism
                 JOIN Gene USING (orgId)
                 JOIN BestHitKEGG USING (orgId,locusId)
                 JOIN KEGGMember USING (keggOrg,keggId)
                 WHERE kgroup IN ( $kgroupSpec )
                 $orgClause
                 LIMIT 100;};
    return $dbh->selectall_arrayref($sql, { Slice => {} });
}

# third argument is a description to do text search on against KgroupDesc.desc
sub matching_kgroup_descs($$$) {
    my ($dbh,$orgId,$geneSpec) = @_;
    die if !defined $dbh || !defined $orgId || !defined $geneSpec;
    # make the query safe and removing leading and trailing space
    $geneSpec =~ s/^ +//;
    $geneSpec =~ s/ +$//;
    $geneSpec =~ s/[\"\n\r]//g;

    my $kgroups = $dbh->selectcol_arrayref(
        qq{ SELECT kgroup from KgroupDesc
           WHERE (desc = "$geneSpec"
                OR desc LIKE "% $geneSpec" OR desc LIKE "$geneSpec %" OR desc LIKE "% $geneSpec %"
                OR desc LIKE "$geneSpec-%" OR desc LIKE "$geneSpec-"
                OR desc LIKE "% $geneSpec-%" OR desc LIKE "%-$geneSpec %"
                OR desc LIKE "$geneSpec/%" OR desc LIKE "%/$geneSpec"
                OR desc LIKE "% $geneSpec/%" OR desc LIKE "%/$geneSpec %"
                OR desc LIKE "$geneSpec,%" OR desc LIKE "% $geneSpec,%") });
    return &matching_kgroup($dbh, $orgId, $kgroups);
}

# third argument is a family identifier or gene name to match against the GeneDomain table
sub matching_domains($$$) {
    my ($dbh,$orgId,$geneSpec) = @_;
    die if !defined $dbh || !defined $orgId || !defined $geneSpec;
    # make the query safe to include in SQL
    $geneSpec =~ s/ +$//;
    $geneSpec =~ s/^ +$//;
    $geneSpec =~ s/[\"\n\r]//g;

    my $orgClause = $orgId eq "" ? "" : qq{ AND orgId = "$orgId"};
    my $sql = qq{SELECT DISTINCT genus, species, strain, orgId, locusId, sysName, gene, domainId, domainName, desc from Gene JOIN Organism USING (orgId) JOIN GeneDomain USING (orgId, locusId)
             WHERE (
                domainId = "$geneSpec" OR domainId LIKE "$geneSpec"
                OR domainName = "$geneSpec" OR domainName LIKE "$geneSpec")                
         $orgClause
         ORDER BY genus, species, strain, locusId, sysName, gene, domainId, domainName
         LIMIT 100;};
         # die $sql;
    return $dbh->selectall_arrayref($sql, { Slice => {} });
}

# third argument is an ec number to match against the GeneDomain table (TIGRFam only)
sub matching_domain_ec($$$) {
    my ($dbh,$orgId,$ecnum) = @_;
    die if !defined $dbh || !defined $orgId || !defined $ecnum;

    my $orgClause = $orgId eq "" ? "" : qq{ AND orgId = "$orgId"};
    my $sql = qq{SELECT DISTINCT genus, species, strain, orgId, locusId, sysName, gene, domainId, domainName, desc
                 FROM Gene JOIN Organism USING (orgId) JOIN GeneDomain USING (orgId, locusId)
                 WHERE ec = ?
                 $orgClause
                 ORDER BY genus, species, strain, locusId, sysName, gene, domainId, domainName
                 LIMIT 100;};
    return $dbh->selectall_arrayref($sql, { Slice => {} }, $ecnum);
}


# Returns a reference to a hash from ortholog's orgId => gene
# Each gene is a hash that includes the fields in Gene and the ratio
sub get_orths($$$) {
    my ($dbh,$orgId,$locusId) = @_;
    die unless defined $orgId && defined $locusId;
    return $dbh->selectall_hashref(qq{ SELECT Gene.*, Ortholog.ratio FROM GENE JOIN ORTHOLOG
					ON Ortholog.orgId2=Gene.orgId AND Ortholog.locusId2=Gene.locusId
					AND orgId1=? AND locusId1=? },
	                           "orgId", {}, $orgId, $locusId);
}

# returns a simple summary of the gene's fitness pattern, like "no data", "weak", "strong", or "cofit",
# and a longer piece of text that can be used as a tooltip
sub gene_fit_string($$$) {
    my ($dbh,$orgId,$locusId) = @_;
    die unless defined $orgId && defined $locusId;
    my ($minFit,$maxFit,$minT,$maxT) = $dbh->selectrow_array(qq{ SELECT min(fit), max(fit), min(t), max(t)
                                                                 FROM GeneFitness WHERE orgId = ? AND locusId = ? ; },
							     {}, $orgId, $locusId);
    return ("no data", "No fitness data for this gene ") if !defined $minFit;
    my $tip = sprintf("fit = %.1f to +%.1f (t = %.1f to +%.1f)", $minFit, $maxFit, $minT, $maxT);
    my ($maxCofit) = $dbh->selectrow_array(qq{ SELECT cofit FROM Cofit WHERE orgId = ? AND locusId = ? AND rank = 1 LIMIT 1; },
					   {}, $orgId, $locusId);
    $tip .= sprintf(", max(cofit) = %.2f", $maxCofit) if defined $maxCofit;
    return ("strong","Strong phenotype: $tip") if ($minT < -5 && $minFit < -2) || ($maxT > 5 && $maxFit > 2);
    return ("cofit","Strong cofitness: $tip") if defined $maxCofit && $maxCofit > 0.75;
    return ("sig.","Significant phenotype: $tip") if ($minT < -4 && $minFit < -1) || ($maxT > 4 && $maxFit > 1);
    return ("insig.", "No significant phenotype: $tip");
}

sub tabsGene($$$$$$$) {
    my($dbh,$cgi,$orgId,$locusId,$showAll,$type,$curr) = @_;
    my $hasFit = gene_has_fitness($dbh, $orgId, $locusId);
    my $hasCofit = gene_has_cofitness($dbh, $orgId, $locusId);
    # print "hasFit ".$hasFit." hasCofit ".$hasCofit;

    my $code = qq[<div id="tabs">];

    my $gClass = "gene";
    $gClass = "selected" if $curr eq "gene";
    $code .= qq[<li class="$gClass"> <a href="geneOverview.cgi?orgId=$orgId&gene=$locusId">Gene</a></li>];

    my $fClass = "gene";
    $fClass = "selected" if $curr eq "fit";
    $fClass = "disable" if $hasFit == 0;

    $code .= qq[<li class="$fClass"> <a href="singleFit.cgi?orgId=$orgId&locusId=$locusId&showAll=0">Fitness</a></li>];
    # magic switching tabs for fitness!
    # if ($showAll == 0) {
    #     my $showAllDest = qq(myFitShow.cgi?orgId=$orgId&gene=$locusId&showAll=1);
    #     $code .= qq[<li class="$fClass"> <a href="$showAllDest">All Fitness Data</a></li>];
    #     # print $cgi->p(qq(<a href=$showAllDest>All fitness data</a>));
    # } else {
    #     my $showFewDest = qq(myFitShow.cgi?orgId=$orgId&gene=$locusId&showAll=0);
    #     $code .= qq[<li class="$fClass"> <a href="$showFewDest">Strongest Phenotypes</a></li>];
    #     # print $cgi->p(qq(<a href=$showFewDest>Strongest phenotypes</a>));
    # }


    my $nClass = "gene";
    $nClass = "selected" if $curr eq "nearby";
    $code .= qq[<li class="$nClass"> <a href="genesFit.cgi?orgId=$orgId&locusId=$locusId&around=2">Nearby</a></li>];
    my ($maxCofit) = $dbh->selectrow_array(qq{ SELECT cofit FROM Cofit WHERE orgId = ? AND locusId = ? AND rank = 1 LIMIT 1; },
                           {}, $orgId, $locusId);

    my $max = sprintf("(max cofit %.2f)", $maxCofit) if defined $maxCofit;
    my $cClass = "gene";
    $cClass = "selected" if $curr eq "cofit";
    $cClass = "disable" if $hasCofit == 0;
    $code .= qq[<li class="$cClass"><a href="cofit.cgi?orgId=$orgId&locusId=$locusId" title="$max">Cofit</a></li>];

    if ($type == 1) {
        my $hClass =  "gene";
        my $pClass = "gene";
        if ($curr eq "protein") {
            $pClass = "selected";
        } elsif ($curr eq "homo") {
            $hClass = "selected";
        }
        $code .= qq[<li class="$pClass"><a href="domains.cgi?orgId=$orgId&locusId=$locusId">Protein</a></li>];
        $code .= qq[<li class="$hClass"><a href="mySeqSearch.cgi?orgId=$orgId&locusId=$locusId">Homologs</a></li>];

    }
    $code .= qq[</div><div id="tabcontent">];

    return $code;
    

#     my @links = ();
#     if ($gene->{locusId} =~ m/^\d+$/) {
#         push @links, $cgi->a({href => "http://www.microbesonline.org/cgi-bin/fetchLocus.cgi?locus=$gene->{locusId}"},
#                  "MicrobesOnline");
#     }
#     if ($orgId eq "Keio" && $gene->{sysName} =~ m/^b\d+$/) {
#         push @links, $cgi->a({href => "http://ecocyc.org/ECOLI/search-query?type=GENE&gname=$gene->{sysName}"}, "EcoCyc");
#     }
#     print $cgi->p("Links: " . join(", ", @links)) if (@links > 0);
# } #  end if just 1 hit
    # $code .= q['']

}

sub tabsExp($$$$$$$) {
    my($dbh,$cgi,$orgId,$expName,$expGroup,$cond,$curr) = @_;
    # print "show: $show, curr: $curr";

    my $code = qq[<div id="tabs">];

    my $oClass = "exp";
    $oClass = "selected" if $curr eq "overview";
    $code .= qq[<li class="$oClass"> <a href="exp.cgi?orgId=$orgId&expName=$expName">Overview</a></li>];

    my $sClass = "exp";
    $sClass = "selected" if $curr eq "specific";
    $code .= qq[<li class="$sClass"> <a href="exp.cgi?orgId=$orgId&expName=$expName&show=specific" title="Specific Phenotypes">Specific</a></li>];

    my $nClass = "exp";
    $nClass = "selected" if $curr eq "-gene"; #and $show eq "important");
    $code .= qq[<li class="$nClass"> <a href="exp.cgi?orgId=$orgId&expName=$expName&show=important" title="Important Genes">- Genes</a></li>];

    my $pClass = "exp";
    $pClass = "selected" if $curr eq "+gene";
    $code .= qq[<li class="$pClass"> <a href="exp.cgi?orgId=$orgId&expName=$expName&show=detrimental" title="Detrimental Genes">+ Genes</a></li>];

    my $mClass = "exp";
    $mClass = "selected" if $curr eq "metrics";
    $code .= qq[<li class="$mClass"><a href="exp.cgi?orgId=$orgId&expName=$expName&show=quality" title="Quality Metrics">Metrics</a></li>];

    # my $cClass = "exp";
    # $cClass = "selected" if $curr eq "compare";
    # $code .= qq[<li class="$cClass"><a href="expComp.cgi?orgId=$orgId&expName=$expName">Compare</a>];

    # if ($type == 1) {
    #     my $hClass, my $pClass = "gene";
    #     if ($curr eq "protein") {
    #         $pClass = "selected";
    #     } elsif ($curr eq "homo") {
    #         $hClass = "selected";
    #     }
    #     $code .= qq[<li class="$pClass"><a href="domains.cgi?orgId=$orgId&locusId=$locusId">Protein</a></li>];
    #     $code .= qq[<li class="$hClass"><a href="mySeqSearch.cgi?orgId=$orgId&locusId=$locusId">Homologs</a></li>];
    # }

    $code .= qq[</div><div id="tabcontent">];

    return $code;

}

# create svg of arrows according to locations of genes. default dimensions 800 (set by $width) x 100. assumes that genes are in order.
# geneSpec can be an empty string if you don't want any of the arrows to be highlighted in red.
# begin and end can be derived from the list if they are not defined
sub geneArrows($$$$) {
    my ($genes, $geneSpec, $begin, $end) = @_;
    $geneSpec = "" if !defined $geneSpec;

    # need extra space for the arrow heads because the are shown slightly past the actual binaries of the gene
    $begin = $genes->[0]->{begin} - 20 if !defined $begin;
    $end = $genes->[-1]->{end} + 20 if !defined $end;
    return "" if $begin > $end;
    my $widthNt = $end - $begin + 1;
    my $width = 800; #'100%'; #input the max-width according to the .arrow class in css
    my $factor = $width/$widthNt;
    my $xScale = 50 * $factor;
    my $scale = 550 * $factor;
    my $xScaleMid = ($xScale+$scale)/2;
    # print $factor;
    # xmlns="http://www.w3.org/2000/svg" height="100" width="$width" viewBox="0 -10 $width 50"

    my $svg = qq[
    <center><svg class="arrows" viewBox="0 -30 $width 100">
    <defs>
    <marker id='rightarrow' orient="auto"
        markerWidth='2' markerHeight='4'
        refX='0.1' refY='2'>
        <!-- triangle pointing right (+x) -->
        <path d='M0,0 V4 L2,2 Z' fill="black"/>
    </marker>
    <marker id='rightarrow2' orient="auto"
        markerWidth='2' markerHeight='4'
        refX='0.1' refY='2'>
        <!-- triangle pointing right (+x) -->
        <path d='M0,0 V4 L2,2 Z' fill="red"/>
    </marker>
    <marker id='leftarrow' orient="auto"
        markerWidth='2' markerHeight='4'
        refX='0.5' refY='2'>
        <!-- triangle pointing left (-x) -->
        <path d='M0,2 L2,0 L2,4 Z' fill="black"/>
    </marker>
    <marker id='leftarrow2' orient="auto"
        markerWidth='2' markerHeight='4'
        refX='0.5' refY='2'>
        <!-- triangle pointing left (-x) -->
        <path d='M0,2 L2,0 L2,4 Z' fill="red"/>
    </marker>
    <marker id="scaleEnd" orient="auto" 
        markerWidth='2' markerHeight='4'
        refX='0.5' refY='2'>
        <line x1="0" y1="5" x2="0" y2="-5" style="stroke: black;"/>
    </marker>
    </defs>

    <line 
        id='scale'
        marker-start='url(#scaleEnd)'
        marker-end='url(#scaleEnd)'
        x1="$xScale" y1="55" x2="$scale" y2="55" style="stroke:black;stroke-width:2" />
    <text x="$xScaleMid" y="50" font-family="Verdana" font-size="10" fill="black" text-anchor="middle">500 nt</text>
    ];
  
    my $pos = 0; # which of 3 rows to put it in
    foreach my $row (@$genes) {
        my $xLeft = ($row->{begin} - $begin) * $factor;
        my $xRight = ($row->{end} - $begin) * $factor;
        my $textX = ($xLeft+$xRight)/2;
        my $textXAdj = $textX - 11-3;
        my $lineY = ($pos+0.1)* 20;
        my $textY = $lineY - 6;
        my $color = "black";
        my $text = "#00A8C6";
        my $head = "marker-end='url(#rightarrow)'";
        $head = "marker-start='url(#leftarrow)'" if $row->{strand} eq "-";
        my $bgcolor = undef;
        if ($row->{locusId} eq $geneSpec) {
            $color = "red";
            $text = "red";
            $head = "marker-end='url(#rightarrow2)'";
            $head = "marker-start='url(#leftarrow2)'" if $row->{strand} eq "-";
            $bgcolor = "#FFFFFF";
        }
        my $label = $row->{gene} || $row->{sysName}; #|| $row->{locusId};
        my $label2 =  $row->{gene} || $row->{sysName} || $row->{locusId};
        my $label3 = $label2;
        $label3 =~ s/^.*_/_/ if $row->{sysName} || $row->{locusId};
        $label2 = $row->{sysName}. ": " . $label2 if $row->{sysName};

        $svg .= qq[
        <g class="click" onclick="window.location.href='singleFit.cgi?orgId=$row->{orgId}&locusId=$row->{locusId}'"><title>$label2 - $row->{desc}, at $row->{begin} to $row->{end}</title><line id='arrow-line' $head x1="$xLeft" y1="$lineY" x2="$xRight" y2="$lineY" style="stroke:$color;stroke-width:2" />
        <text x="$textXAdj" y="$textY" font-family="Verdana" font-size="13" fill="$text" onmouseover="this.style.fill='#CC0024'" onmouseout="this.style.fill='#00A8C6'">$label3</text></g>];

        $pos = ($pos+1) % 3;
    }
    $svg .= "</svg></center>";
    return $svg;
}

sub site_intro_text {
    if (-e "../motd") {
        open(MOTD, "<", "../motd");
        my @lines = <MOTD>;
        close(MOTD);
        return join("",@lines) if @lines > 0;
    }
    #else
    return CGI::h5(q{Browse thousands of <i>mostly unpublished</i> fitness experiments from the
     Deutschbauer lab,
     the <A HREF="http://genomics.lbl.gov/">Arkin lab</A>,
     and collaborators. Contact <A HREF="mailto:AMDeutschbauer.lbl.gov">Adam Deutschbauer</A> for more information.});
}

sub commify($) {
    local $_  = shift;
    1 while s/^(-?\d+)(\d{3})/$1,$2/;
    return $_;
}

sub OrgSelector($$) {
    my ($orgDefault,$orginfo) = @_;
    my $out = qq{ <SELECT name="orgId"> };
    my %orgNames = map { $_ => $orginfo->{$_}{genome} } keys(%$orginfo);
    my @orgs = sort { $orgNames{$a} cmp $orgNames{$b} } keys(%orgNames);
    foreach my $orgId (@orgs) {
        my $selected = $orgId eq $orgDefault ? "SELECTED" : "";
        $out .= qq{ <option value="$orgId" $selected >$orgNames{$orgId}</option> };
    }
    $out .= "</select>";
    return $out;
}

# dbh,orgId,locusId => undef (no information) or a hash that includes
# orgId, locusId, keggOrg, keggId, identity, and ko (ortholog group), which is a list
# each entry in ko is a hash of kgroup, desc, and ec, which is a list of ec numbers
# Note -- ko may be empty
sub kegg_info($$$) {
    my ($dbh,$orgId,$locusId) = @_;
    die "Invalid arguments to kegg_info"
        unless defined $dbh && defined $orgId && defined $locusId
        && $orgId ne "" && $locusId ne "";
    my $bhKEGG = $dbh->selectrow_hashref("SELECT * from BestHitKEGG where orgId = ? AND locusId = ?",
                                         {}, $orgId, $locusId);
    return undef unless defined $bhKEGG->{keggId};
    my $keggOrg = $bhKEGG->{keggOrg};
    my $keggId = $bhKEGG->{keggId};
    my $ko = $dbh->selectall_arrayref("SELECT * from KEGGMember JOIN KgroupDesc USING (kgroup)
                                       WHERE keggOrg = ? AND keggId = ?",
                                      { Slice => {} }, $keggOrg, $keggId);
    foreach my $row (@$ko) {
        my $ecs = $dbh->selectcol_arrayref("SELECT ecnum FROM KgroupEC WHERE kgroup = ?",
                                           {}, $row->{kgroup});
        $row->{ec} = $ecs;
    }
    $bhKEGG->{ko} = $ko;
    return $bhKEGG;
}

# dbh,orgId,locusId => list of seed_description (or undef), list of seed classes (EC or TC)
sub seed_desc($$$) {
    my ($dbh,$orgId,$locusId) = @_;
    die "Invalid arguments to seed_desc"
        unless defined $dbh && defined $orgId && defined $locusId
        && $orgId ne "" && $locusId ne "";
    my ($seed_desc) = $dbh->selectrow_array("SELECT seed_desc FROM SEEDAnnotation WHERE orgId = ? AND locusId = ?",
                                            {}, $orgId, $locusId);
    my $seed_classes = $dbh->selectall_arrayref("SELECT type,num FROM SEEDClass WHERE orgId = ? AND locusId = ?",
                                                {}, $orgId, $locusId);
    return ($seed_desc,$seed_classes);
}

# Caching to speed up alt_descriptions() on pages that list a gene more than once
my %altdesccache = (); # org => locusId => text

# dbh,orgId,locusId => text showing alternate descriptions for the gene (or an empty string)
# Uses its own queries instead of kegg_info() and seed_desc() for performance.
# (To really speed it up I could have the option of providing locusId as a list to
# pre-cache all those genes with just 1 query)
sub alt_descriptions($$$) {
    my ($dbh, $orgId, $locusId) = @_;
    die "Invalid arguments to alt_descriptions"
        unless defined $dbh && defined $orgId && defined $locusId
        && $orgId ne "" && $locusId ne "";
    return $altdesccache{$orgId}{$locusId} if exists $altdesccache{$orgId}{$locusId};

    my ($reannotation) = $dbh->selectrow_array("SELECT new_annotation FROM Reannotation WHERE orgId = ? AND locusId = ?",
                                               {}, $orgId, $locusId);
    my ($seed_desc) = $dbh->selectrow_array("SELECT seed_desc FROM SEEDAnnotation WHERE orgId = ? AND locusId = ?",
                                            {}, $orgId, $locusId);
    my $kegg_descs = $dbh->selectcol_arrayref("SELECT DISTINCT KgroupDesc.desc
                                               FROM BestHitKEGG JOIN KEGGMember USING (keggOrg,keggId)
                                               JOIN KgroupDesc USING (kgroup)
                                               WHERE orgId = ? AND locusId = ? AND desc <> ''",
                                              {}, $orgId, $locusId);

    my @altdesc = ();
    push @altdesc, "Reannotation: $reannotation" if defined $reannotation;
    push @altdesc, "SEED: $seed_desc" if defined $seed_desc;
    push @altdesc, "KEGG: " . join("; ", @$kegg_descs)
            if scalar(@$kegg_descs) > 0;
    $altdesccache{$orgId}{$locusId} = join(";&nbsp; ", @altdesc);
    return $altdesccache{$orgId}{$locusId};
}

# a link to the gene by its description
# The first argument is the dbh
# The second argument is the gene row
# The third argument is whether to show the name or the description ("name" or "desc")
# The final argument is which cgi to use (usually myFitShow.cgi)
sub gene_link {
  my ($dbh, $gene, $showParam, $cgiParam) = @_;
  die "Unrecognized $showParam" unless $showParam eq "name" || $showParam eq "desc";
  die "Must specify cgi" unless defined $cgiParam;
  $cgiParam = "singleFit.cgi" unless $cgiParam;
  my $desc = $gene->{desc};
  $desc =~ s/"//g;
  my $alt_desc = Utils::alt_descriptions($dbh,$gene->{orgId},$gene->{locusId});
  my $desc_long;
  if ($showParam eq "desc") {
    $desc_long = $alt_desc || "No further information";
  } else {
    $desc_long = $desc;
    $desc_long .= "; $alt_desc" if $alt_desc;
  }
  $desc_long =~ s/&nbsp;//g;
  my $show = $showParam eq "name" ? $gene->{sysName} || $gene->{locusId} : $gene->{desc} || "no description";
  return CGI::a({ -href => "$cgiParam?orgId=$gene->{orgId}&gene=$gene->{locusId}",
                  -title => $desc_long },
                $show);
}

# dbh, orgId, ref. to list of ec numbers => hashref of ecnum to locusId => 1
# Note that EC number searches (in myFitShow.cgi) do NOT use this function
sub EcToGenes($$$) {
    my ($dbh,$orgId,$ecnums) = @_;
    return {} if @$ecnums == 0;
    my %ecGenes = (); # ecnum => locusId => 1
    my @ecspecs = map "'" . $_ . "'", @$ecnums;
    my $ecspec = join(",", map "'" . $_ . "'", @$ecnums);
    # match ECs by TIGRFam, by KEGG ortholog group, and by SEED annotation
    my $hits1 = $dbh->selectall_arrayref(
	qq{ SELECT ec, locusId FROM GeneDomain JOIN Gene USING (orgId,locusId)
            WHERE orgId = ? AND ec IN ( $ecspec ); },
        {}, $orgId);
    my $hits2 = $dbh->selectall_arrayref(
        qq{ SELECT ecnum, locusId FROM KgroupEC JOIN KEGGMember USING (kgroup)
            JOIN BestHitKEGG USING (keggOrg,keggId)
            WHERE orgId = ? AND ecnum IN ( $ecspec ); },
        {}, $orgId);
                                                 
    my $hits3 = $dbh->selectall_arrayref(
        qq{ SELECT num,locusId
		FROM SEEDClass JOIN SEEDAnnotation USING (orgId,locusId)
                WHERE orgId = ? AND num IN ( $ecspec ); },
        {}, $orgId);
    foreach my $hits ($hits1,$hits2,$hits3) {
        foreach my $row (@$hits) {
            my ($ec,$locusId) = @$row;
            $ecGenes{$ec}{$locusId} = 1;
        }
    }
    return \%ecGenes;
}

#END 

return 1;

