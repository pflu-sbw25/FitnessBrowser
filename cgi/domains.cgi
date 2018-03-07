#!/usr/bin/perl -w

#######################################################
## domains.cgi -- sequence analysis of a protein
##
## Copyright (c) 2015 University of California
##
## Authors:
## Victoria Lo and Morgan Price
#######################################################
#
# Required CGI parameters:
# orgId -- which organism
# locusId (or gene) -- which locus

use strict;
use CGI qw(:standard Vars start_ul);
use CGI::Carp qw(warningsToBrowser fatalsToBrowser);
use DBI;
use Bio::SeqIO;

use lib "../lib";
use Utils;

my $cgi=CGI->new;

my $orgId = $cgi->param('orgId') || die "No orgId parameter";
my $locusId = $cgi->param('locusId') || $cgi->param('gene') || die "No locusId or gene parameter";

my $dbh = Utils::get_dbh();
my $orginfo = Utils::orginfo($dbh);
die "Unknown organism" unless $orgId eq "" || exists $orginfo->{$orgId};
my $gene = $dbh->selectrow_hashref("SELECT * FROM Gene WHERE orgId=? AND locusId=?",
				   {}, $orgId, $locusId);

die "Unknown gene" unless defined $gene->{locusId};

if ($gene->{type} != 1) {
    # this can be reached by some links from gene descriptions
    # redirect to the gene overview page if not a protein
    print redirect(-url => "geneOverview.cgi?orgId=$orgId&gene=$locusId");
}

# write the title
my $title = "Protein Info for $orginfo->{$orgId}{genome} at Locus $locusId";
my $start = Utils::start_page("$title");

my $tabs = Utils::tabsGene($dbh,$cgi,$orgId,$locusId,0,1,"protein");

# domains table
# gather data and slice it into an array of hashes
my $cond = $dbh->selectall_arrayref(qq{SELECT domainDb, orgId, locusId, domainId, domainName, begin, end, score, evalue, definition, ec FROM GeneDomain WHERE orgId=? AND locusId=? ORDER BY begin;},
    { Slice => {} },
    $orgId, $locusId);

#find length of sequence
my $tmpDir = Utils::tmp_dir();
my $seqFile = "$tmpDir/$orgId+$locusId.fasta";
my $myDB = Utils::blast_db();
my $id = join(":",$orgId,$locusId);
my $fastacmd = '../bin/blast/fastacmd';
system($fastacmd,'-d',$myDB,'-s',$id,'-o',$seqFile)==0 || die "Error running $fastacmd -d $myDB -s $id -o $seqFile -- $!";
my $in = Bio::SeqIO->new(-file => $seqFile,-format => 'fasta');
my $seq = $in->next_seq()->seq;
my $seqLen = length($seq);
unlink($seqFile) || die "Error deleting $seqFile: $!";


my $sys = $gene->{sysName} || $gene->{locusId};

my @toplines = ();
push @toplines, "Name: $gene->{gene}" if $gene->{gene} ne "";
push @toplines, "Description: $gene->{desc}";

# Reannotation information, if any
my $reanno = $dbh->selectrow_hashref("SELECT * from Reannotation WHERE orgId = ? AND locusId = ?",
                                     {}, $orgId, $locusId);
if ($reanno->{new_annotation}) {
    push @toplines,
    "Updated annotation: $reanno->{new_annotation}",
    small("Rationale:", $reanno->{comment} );
}

print
    header, $start, $tabs, '<div id="tabcontent">',
    h2("Protein Info for $sys in " . $cgi->a({href => "org.cgi?orgId=$orgId"},$orginfo->{$orgId}{genome})),
    p(join("<BR>", @toplines)),
    h3("Domains and Families");

my %ecall = (); # ec number => source => 1
# (source is one of TIGRFam, KEGG, SEED, reanno, MetaCyc)

if (@$cond == 0) {
    print "No PFam or TIGRFam domains were found in this protein."
} else {
    #create domains table
    my @headings = qw{Family ID Coverage EValue}; # Begin End};
    my @trows = ( Tr({ -valign => 'top', -align => 'center' }, map { th($_) } \@headings) );
    foreach my $row (@$cond) {
        # display result row by row
        my $len = $row->{end}-$row->{begin}; 
        my $begin = $row->{begin};
        my $newBegin = $begin;
        my $newLen = $len;
        my $newSeqLen = $seqLen;
        if ($seqLen > 600) {
            $newBegin = 600*$begin/$seqLen;
            $newLen = 600*$len/$seqLen;
            $newSeqLen = 600;
        }
        if ($row->{domainDb} eq 'PFam') {
            push @trows, Tr({ -valign => 'top', -align => 'left' },
                            td([ $row->{domainName}, #name/description
                                 a({href => "http://pfam.xfam.org/family/$row->{domainId}"},
                                   $row->{domainId}), #ID
                                 a({title=>"Amino acids $begin to $row->{end} ($len) of $seqLen"}, div({class=>"line"}, img({src=>"../images/grayHorizLine.png", width=>"$newSeqLen", height=>'7'}), div({class=>"line2", style=>"left:$newBegin".'px'}, img({src=>"../images/darkcyan.png", height=>'7', width=>"$newLen"})))),#$len, # $row->{}, #length diagram: end-begin
                                 # $row->{score}, #score
                                 a({title=>"Score: $row->{score}"},$row->{evalue}), #evalue with hover score
                                 # $row->{begin}, #begin
                                 # $row->{end}, #end
                               ]));
        } elsif ($row->{domainDb} eq 'TIGRFam') {
            push @trows, Tr({ -valign => 'top', -align => 'left' },
                            td([ $row->{definition} || $row->{domainName}, #name/description
                                 a({href => "http://www.jcvi.org/cgi-bin/tigrfams/HmmReportPage.cgi?acc=$row->{domainId}"},
                                   $row->{domainId}), #ID
                                 a({title=>"Amino acids $begin to $row->{end} ($len) of $seqLen"}, div({class=>"line"}, img({src=>"../images/grayHorizLine.png", width=>"$newSeqLen", height=>'7'}), div({class=>"line2", style=>"left:$newBegin".'px'}, img({src=>"../images/chocolate.png", height=>'7', width=>"$newLen"})))), # $len, # $row->{}, #length diagram: end-begin
                                 # $row->{score}, #score
                                 a({title=>"Score: $row->{score}"},$row->{evalue}), #evalue with hover score
                                 # $row->{begin}, #begin
                                 # $row->{end}, #end
                               ]));
            $ecall{ $row->{ec} }{"TIGRFam"} = 1 if $row->{ec} ne "";
        }
    }
    print table({cellspacing => 0, cellpadding => 3}, @trows);
}

print h3("Best Hits");

# UniProt information, if any
my $bhSprot = $dbh->selectrow_hashref("SELECT * from BestHitSwissProt
                                         JOIN SwissProtDesc USING (sprotAccession,sprotId)
                                         WHERE orgId = ? AND locusId = ?",
                                      {}, $orgId, $locusId);
if (defined $bhSprot->{sprotAccession}) {
    my $acc = $bhSprot->{sprotAccession};
    print
        p("Swiss-Prot:",
            sprintf("%.0f%% identical to", $bhSprot->{identity}),
            a({ href => "http://www.uniprot.org/uniprot/$acc",
                title => $bhSprot->{sprotAccession} },
              $bhSprot->{sprotId} ) . ":",
            $bhSprot->{desc},
            $bhSprot->{geneName} ? "($bhSprot->{geneName})" : "",
            "from",
            $bhSprot->{organism} );
}
print "\n";

# KEGG information, if any
my $kegg = Utils::kegg_info($dbh, $orgId, $locusId);
if (defined $kegg) {
    my $ko = $kegg->{ko};
    my @kopieces = ();
    if (scalar(@{ $kegg->{ko} }) > 0) {
        foreach my $row (@$ko) {
            my $ecs = $row->{ec};
            my @ecdesc = ();
            foreach my $ec (@$ecs) {
                if ($ec =~ m/-/) {
                    push @ecdesc, $ec;
                } else {
                    push @ecdesc, a({-href => "http://www.kegg.jp/dbget-bin/www_bget?ec:$ec"}, $ec);
                }
                $ecall{$ec}{"KEGG"} = 1;
            }
            my $ecdesc = join(" ", @ecdesc);
            $ecdesc = " [EC: $ecdesc]" if $ecdesc ne "";

            push @kopieces,
              join("",
                   a({-href => "http://www.kegg.jp/dbget-bin/www_bget?ko:" . $row->{kgroup}},
                     $row->{kgroup}),
                   ", ",
                   $row->{desc} || "(no description)",
                   $ecdesc);
        }
    } else {
      push @kopieces, "None";
    }
    my $keggOrg = $kegg->{keggOrg};
    my $keggId = $kegg->{keggId};
    print join(" ", "KEGG orthology group:", @kopieces,
               sprintf("(inferred from %.0f%% identity to ", $kegg->{identity}),
               a({-href => "http://www.kegg.jp/dbget-bin/www_bget?$keggOrg:$keggId"},
                 "$keggOrg:$keggId").")");
}
print "\n";

# MetaCyc information, if any
my $bhMetacyc = $dbh->selectall_arrayref(qq{ SELECT * FROM BestHitMetacyc
                                             LEFT JOIN MetacycReaction USING (rxnId)
                                             WHERE orgId = ? AND locusId = ?
                                             ORDER BY rxnName DESC },
                                         { Slice => {} }, $orgId, $locusId);
my %metacycrxn = (); # which reactions are linked to
if (scalar(@$bhMetacyc) > 0) {
  my @showrxns = ();
  my @showecs = ();
  my %ecSeen = ();
  # Multiple hits if gene is linked to >1 reaction
  foreach my $row (@$bhMetacyc) {
    my $ecnums = $dbh->selectcol_arrayref("SELECT ecnum from MetacycReactionEC WHERE rxnId = ?",
                                          {}, $row->{rxnId});
    my $rxnName = $row->{rxnName} || "";
    $metacycrxn{ $row->{rxnId} } = 1;
    foreach my $ec (@$ecnums) {
      next if exists $ecSeen{$ec};
      $ecSeen{$ec} = 1;
      $ecall{$ec}{"MetaCyc"} = 1;
      push @showecs, $ec;
      # and maybe update the name

      # If no reaction name, or it is just some EC number(s) --
      # replace with KEGG description of first ec
      if ($rxnName eq "" || $rxnName =~ m/^[0-9][.][0-9.,]+$/) {
        ($rxnName) = $dbh->selectrow_array("SELECT ecdesc FROM ECInfo WHERE ecnum = ?",
                                           {}, $ec);
      }
    }
    $rxnName = $row->{rxnId} if $rxnName eq "";
    my $showrxn = a({ -href => "http://metacyc.org/META/NEW-IMAGE?type=REACTION&object=" . $row->{rxnId},
                      -title => "see $row->{rxnId} in MetaCyc" },
                 $rxnName);
    if (@showecs > 0) {
      @showecs = map a({ -href => "https://metacyc.org/META/NEW-IMAGE?type=EC-NUMBER&object=EC-$_" }, $_), @showecs;
      $showrxn .= " [EC: " . join(", ", @showecs) . "]";
    }
    push @showrxns, $showrxn;
  }
  my $row = $bhMetacyc->[0];
  my $acc = $row->{sprotAccession};
  print
      p("MetaCyc:",
        sprintf("%.0f%% identical to", $row->{identity}),
        a({ href => "http://www.uniprot.org/uniprot/$acc" }, $acc) . ": " .
        join("; ", @showrxns)
       );
}
print "\n";

# SEED information, if any
my @show_classes = ();
my ($seed_desc,$seed_classes) = Utils::seed_desc($dbh,$orgId,$locusId);
foreach my $row (@$seed_classes) {
    my ($type,$num) = @$row;
    my $url_pre = $type == 1 ? "http://www.kegg.jp/dbget-bin/www_bget?ec:"
        : "http://www.tcdb.org/search/result.php?tc=";
    my $text = ($type == 1 ? "EC " : "TC ").$num;
    push @show_classes, ($num =~ m/-/ ? $text
                         : a({-href => $url_pre . $num}, $text));
    $ecall{$num}{"SEED"} = 1 if $type == 1;
}
my $subsysShow = "";
if ($seed_desc) {
  my $subsysList = $dbh->selectcol_arrayref(qq{ SELECT DISTINCT subsystem FROM SeedAnnotationToRoles
                                                JOIN SEEDRoles USING (seedrole)
                                                WHERE seed_desc = ? },
                                            {}, $seed_desc);
  my @subsysShow = ();
  foreach my $subsys (@$subsysList) {
    my $nice = $subsys; $nice =~ s/_/ /g;
    push @subsysShow, a({ -href => "seedsubsystem.cgi?orgId=$orgId&subsystem=$subsys" },
                        $nice);
  }
  $subsysShow = " in subsystem " . join(" or ", @subsysShow) if @subsysShow > 0;
}

print
    h3("Predicted SEED Role"),
    p(defined $seed_desc ?  '"' . $seed_desc . '"' . $subsysShow : "No annotation",
      @show_classes > 0 ? "(" . join(", ", @show_classes) . ")" : "");
print "\n";

# And add reannotated EC numbers to %ecall
# (Above we already did TIGRFam, KEGG, SEED)
my $reannoEc = $dbh->selectcol_arrayref(qq{ SELECT ecnum FROM ReannotationEC
                                            WHERE orgId = ? AND locusId = ? },
                                        {}, $orgId, $locusId);
foreach my $ec (@$reannoEc) {
  $ecall{$ec}{"reanno"} = 1;
}

# Ok, now we have all the EC numbers, link to MetaCyc pathways and to KEGG maps
# MetaCyc pathways
my @ec = sort keys %ecall;
# ecGenes will store the mapping of ec => hash of potential locusIds in this genome
# This is both for isozymes and for other reactions in relevant pathways.
my $ecGenes;

if (@ec > 0 || keys(%metacycrxn) > 0) {
  # Expand the list of potential MetaCyc reactions by using EC numbers
  foreach my $ec (@ec) {
    my $ecrxns = $dbh->selectcol_arrayref("SELECT rxnId FROM MetacycReactionEC WHERE ecnum = ?",
                                          {}, $ec);
    foreach my $rxnId (@$ecrxns) {
      $metacycrxn{$rxnId} = 1;
    }
  }

  # Find all relevant MetaCyc pathways, using MetacycPathwayReaction
  my %pathways = (); # pathwayId => pathName
  foreach my $rxnId (keys %metacycrxn) {
    my $paths = $dbh->selectall_arrayref(qq{ SELECT pathwayId, pathwayName
                                             FROM MetacycPathwayReaction JOIN MetacycPathway USING (pathwayId)
                                             WHERE rxnId = ? },
                                         {}, $rxnId);
    foreach my $paths (@$paths) {
      my ($pathId, $pathName) = @$paths;
      $pathways{$pathId} = $pathName;
    }
  }

  # List the EC numbers in those pathways
  my %pathwayEC = (); # pathway => EC => 1 if present in genome, 0 otherwise
  my %ec2 = %ecall;
  foreach my $pathId (keys %pathways) {
    my $ecs = $dbh->selectcol_arrayref(qq{ SELECT ecnum FROM MetacycPathwayReaction
                                           JOIN MetacycReactionEC USING (rxnId)
                                           WHERE pathwayId = ? },
                                       {}, $pathId);
    $pathwayEC{$pathId} = $ecs;
    foreach my $ec (@$ecs) {
      $ec2{$ec} = 1;
    }
  }

  # Find all genes that may be mapped to those EC
  my @ec2 = keys %ec2;
  $ecGenes = Utils::EcToGenes($dbh, $orgId, \@ec2);

  # Relevance of each pathway
  my %pathCount = (); # pathId => [#reactions, #found, score ]
  foreach my $pathId (keys %pathways) {
      my $ecs = $pathwayEC{$pathId};
      my $n = scalar(@$ecs);
      my $nFound = 0;
      foreach my $ec (@$ecs) {
        $nFound++ if exists $ecGenes->{$ec} && scalar(keys %{ $ecGenes->{$ec} }) > 0;
      }
      # score is nFound - nMissing (higher is better)
      $pathCount{$pathId} = [ $n, $nFound, $nFound - ($n-$nFound) ];
  }
  # sort by higher score, or by fewer missing, or by name (alphabetically)
  my @path = sort { $pathCount{$b}[2] - $pathCount{$a}[2]
                      || $pathCount{$a}[1] - $pathCount{$b}[1]
                        || $pathways{$a} cmp $pathways{$b}
                      }  keys %pathways;

  # Show a list of links to pathways
  my @pathList = ();
  foreach my $pathId (@path) {
    my ($n,$nFound) = @{ $pathCount{$pathId} };
    push @pathList, li(a( {-href => "https://metacyc.org/META/NEW-IMAGE?type=PATHWAY&object=" . $pathId},
                          $pathways{$pathId} ),
                       "($nFound/$n steps found)");
  }
  print h3("MetaCyc Pathways"), start_ul(), join("\n", @pathList), end_ul(), "\n"
    if @pathList > 0;
}

# KEGG maps
if (keys(%ecall) > 0) {
    my @ec = sort keys %ecall;

    my @ecspec = map { "'" . $_ . "'" } @ec;
    my $ecspec = join(",", @ecspec);
    my $maps = $dbh->selectall_arrayref(qq{SELECT DISTINCT mapId,title
                                           FROM KEGGConf JOIN KEGGMap USING (mapId)
                                           WHERE type=1 AND objectId IN ( $ecspec )
                                           ORDER BY title});
    if (scalar(@$maps) > 0) {
        my @rendered = ();
        foreach my $row (@$maps) {
            my ($mapId,$mapdesc) = @$row;
            push @rendered, li(a({href => "keggmap.cgi?orgId=$orgId&mapId=$mapId&ec="
                                      . join(",", @ec)},
                                 $mapdesc));
        }
        print
            h3("KEGG Metabolic Maps"),
            "<ul>",
            join("", @rendered),
            "</ul>";
    }

    my @links = ();
    foreach my $ec (@ec) {
        my @iso = keys %{ $ecGenes->{$ec} };
        my @iso2 = grep { $_ ne $locusId } @iso;
        if (@iso2 > 0) {
            my @locusSpecs = map "locusId=$_", @iso;
            push @links, a( { -href => "genesFit.cgi?orgId=$orgId&" . join("&", @locusSpecs) },
                            $ec );
        }
    }
    print
        h3("Isozymes"),
        scalar(@links) > 0 ? p("Compare fitness of isozymes for:", join(", ", @links))
        : "No predicted isozymes";
}

# print sequence
$seq =~ s/(.{60})/$1\n/gs;
my $desc = $gene->{desc};
$desc =~ s/"//g;
my $orgtype = "bacteria";
my $gram = "negative";
my $newline = "%0A";

print
    h3("Sequence Analysis Tools"),
    p(a({-href => "http://papers.genomics.lbl.gov/cgi-bin/litSearch.cgi?query=>${sys}$newline$seq"},
        "PaperBLAST"),
      "(search for papers about homologs of this protein)"),
    p(a({-href => "http://www.ncbi.nlm.nih.gov/Structure/cdd/wrpsb.cgi?seqinput=>${sys}$newline$seq"},
        "Search CDD"),
      "(the Conserved Domains Database, which includes COG and superfam)"),

    p(a({-href => "http://pfam.xfam.org/search/sequence?seqOpts=&ga=0&evalue=1.0&seq=$seq"},
        "Search PFam"),
      "(including for weak hits, up to E = 1)"),

    p("Predict protein localization: ",
      a({-href => "http://www.psort.org/psortb/results.pl?"
             . join("&",
                    "organism=$orgtype",
                    "gram=$gram",
                    "format=html",
                    "sendresults=display",
                    "email=",
                    "seqs=>${sys}$newline$seq")},
        "PSORTb"),
      "(Gram $gram $orgtype)"),

    p("Predict transmembrane helices:",
      a({-href => "http://www.cbs.dtu.dk/cgi-bin/webface2.fcgi?"
             . join("&",
                    "configfile=/usr/opt/www/pub/CBS/services/TMHMM-2.0/TMHMM2.cf",
                    "outform=-noshort",
                    "SEQ=>${sys}$newline$seq")},
        "TMHMM")),

    p("Check the current SEED with",
      # %0A encodes "\n" so that it looks like fasta input.
      a({-href => "http://pubseed.theseed.org/FIG/seedviewer.cgi?page=FigFamViewer&fasta_seq=>${sys}%0A$seq"},
        "FIGfam search")),


    h3("Protein Sequence ($seqLen amino acids)"),
    pre(">$sys $gene->{desc} ($orginfo->{$orgId}{genome})\n$seq"),

    '</div>';

$dbh->disconnect();
Utils::endHtml($cgi);
