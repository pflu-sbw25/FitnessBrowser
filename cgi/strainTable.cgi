#!/usr/bin/perl -w
#######################################################
## strainTable.cgi
##
## Copyright (c) 2015 University of California
##
## Authors:
## Morgan Price
#######################################################
#
# Required CGI parameters:
# orgId -- which organism
# and either
#	scaffoldId, begin, end -- the range of interest (limited to 50 kb)
# or
#	locusId -- which gene to show (by default, range is exactly the width of the gene)
# Optional CGI parameters:
# expName -- which experiments to show. (Can be more than one.)
# addexp -- additional experiments (i.e. a setname or a condition)
# zoom -- in or out
# pan -- left or right

use strict;
use CGI qw(-nosticky :standard Vars);
use CGI::Carp qw(warningsToBrowser fatalsToBrowser);
use DBI;

use lib "../lib";
use Utils;
use StrainFitness;
sub commify($);

my $cgi=CGI->new;
my $style = Utils::get_style();
my $dbh = Utils::get_dbh();
my $orginfo = Utils::orginfo($dbh);
my $orgId = $cgi->param('orgId') || die "No orgId found";
my $genome = $orginfo->{$orgId}{genome} || die "Invalid orgId $orgId";

my @expNames = $cgi->param('expName');
my $scaffoldId = $cgi->param('scaffoldId');
my $begin = $cgi->param('begin');
my $end = $cgi->param('end');
my $locusSpec = $cgi->param('locusId');
my $locusSpecShow;
my $tsv = $cgi->param('tsv') || 0;
my $expName = $cgi->param('expName') || "";

if (defined $locusSpec && $locusSpec ne "") {
    my $sysName;
    ($scaffoldId,$begin,$end,$sysName) = $dbh->selectrow_array(
        "SELECT scaffoldId,begin,end,sysName FROM Gene WHERE orgId = ? AND locusId = ?",
        {}, $orgId, $locusSpec);
    die "Unknown locus $locusSpec in $orgId" if !defined $end;
    $locusSpecShow = $sysName || $locusSpec;
    my $widen = int(1 + 0.2 * ($end-$begin+1));
    $begin -= $widen;
    $end += $widen;
} elsif (defined $scaffoldId && defined $begin && defined $end) {
    die "Invalid scaffold parameter" if $scaffoldId eq "";
    die "Invalid begin parameter" unless $begin =~ m/^-?\d+$/;
    die "Invalid end parameter" unless $end =~ m/^\d+$/;
}
my $zoom = $cgi->param('zoom');
my $initwidth = $end - $begin + 1;
if ($zoom eq "in") {
    $begin += 0.2 * $initwidth;
    $end -= 0.2 * $initwidth;
} elsif ($zoom eq "out") {
    $begin -= 0.4 * $initwidth;
    $end += 0.4 * $initwidth;
}
my $pan = $cgi->param('pan');
if ($pan eq "left") {
    
    $begin -= 0.4 * $initwidth;
    $end -= 0.4 * $initwidth;
} elsif ($pan eq "right") {
    $begin += 0.4 * $initwidth;
    $end += 0.4 * $initwidth;
}
$begin = int($begin);
$end = int($end);

$end = $begin + 1 if $begin eq $end;
unless ($begin < $end) {
    print $cgi->header;
    Utils::fail($cgi, "Invalid begin/end $begin $end")
}
my $maxWidth = 25*1000;
if ($end - $begin >= $maxWidth) {
    print $cgi->header;
    Utils::fail($cgi, "Too wide, the limit is to show a range of " . &commify($maxWidth) . " nucleotides");
}

my $addexp = $cgi->param('addexp');

# additional experiments?
if (defined $addexp && $addexp ne "") {
    my @expsNew = @{ Utils::matching_exps($dbh,$orgId,$addexp) };
    if (@expsNew == 0) {
        print header;
        Utils::fail($cgi, qq{No experiment matching "$addexp"}); # XXX
    }
    # else
    my %oldExps = map { $_ => 1 } @expNames;
    push @expNames, grep {!exists $oldExps{$_} } map { $_->{expName} } @expsNew;
}

my $expinfo = Utils::expinfo($dbh,$orgId);
foreach my $expName (@expNames) {
    die "No such experiment: $expName" unless exists $expinfo->{$expName};
}

my $begComma = &commify($begin);
my $endComma = &commify($end);

#make tsv here? debate in printing first vs. running db commands
print header;
if ($tsv != 1) {
    print
        Utils::start_page("Strain Fitness in $genome"),
        q{<div id="ntcontent">},
        h2("Strain Fitness in ",
           a({-href => "org.cgi?orgId=$orgId"}, "$genome"),
           defined $locusSpecShow ? "around " . a({-href => "singleFit.cgi?orgId=$orgId&locusId=$locusSpec"}, $locusSpecShow)
           : " at $scaffoldId: $begComma to $endComma"),
        start_form(-name => 'input', -method => 'GET', -action => 'strainTable.cgi'),
        hidden( -name => 'orgId', -value => $orgId, -override => 1),
        hidden( -name => 'scaffoldId', -value => $scaffoldId, -override => 1),
        hidden( -name => 'begin', -value => $begin, -override => 1),
        hidden( -name => 'end', -value => $end, -override => 1),
        join("\n", map { hidden( -name => 'expName', -value => $_, -override => 1) } @expNames),
        p(
          "Add experiment(s): ",
          textfield(-name => 'addexp', -default => "", -override => 1, -size => 20, -maxLength => 100)),
        p({-class => "buttons", style=>"max-width:500px; line-height:40px; white-space:nowrap;"}, "Zoom:", submit('zoom','in'), submit('zoom','out'), "\tPan:", submit('pan','left'), submit('pan','right')),
        end_form,
        p(small("Only strains with sufficient reads to estimate fitness are shown, but the strain fitness values are still rather noisy. Strains near the edge of a gene are not shown as being associated with that gene (the Gene column will be empty)."));


    if (defined $begin and defined $end and defined $scaffoldId) {
        # foreach my $locusId (@locusIds) {
            my $genes = $dbh->selectall_arrayref("SELECT * FROM Gene WHERE orgId = ? AND scaffoldId = ? AND Gene.end >= ? AND Gene.begin <= ?",
                               { Slice => {} }, $orgId, $scaffoldId, $begin, $end);
            if (@$genes == 0) {
                print "No genes in range.";
            } else {
                sort @$genes;
                # foreach my $genea(@$genes) {
                #     print $genea->{begin} . "\t" . $genea->{end} . "\t";
                # }
                print Utils::geneArrows(\@$genes, "");
            }
    }
}


# should I add zoom in/out and pan left/right buttons??
my $rows = StrainFitness::GetStrainFitness("../cgi_data", $dbh, $orgId, $scaffoldId, $begin, $end);

if (@$rows == 0) {
    print "No fitness data for strains in range " . commify($begin) . " to " . commify($end) . "\n";
}
my @trows = (); # the table
# header row
my @headings = qw{Position Strand Gene};
push @headings, a({-title => "Fractional position within gene"}, "Fraction");
foreach my $expName (@expNames) {
    push @headings, a({-href => "exp.cgi?orgId=$orgId&expName=$expName", -title => $expName},
                      $expinfo->{$expName}{expDesc});
}
push @trows, Tr({-align => 'CENTER', -valign=>'TOP'}, th(\@headings));

# leave out gene if not a used strain
foreach my $row (@$rows) {
    $row->{locusId} = "" unless $row->{used} eq "TRUE";
}
my %locusIds = map { $_->{locusId} => 1 } @$rows;
my %genes = (); # locusId => row
foreach my $locusId (keys %locusIds) {
    next if $locusId eq "";
    my $gene = $dbh->selectrow_hashref("SELECT * FROM Gene WHERE orgId = ? AND locusId = ?",
                                       {}, $orgId, $locusId);
    die "Unknown locusId $locusId" unless exists $gene->{locusId};
    $genes{$locusId} = $gene;
}


my @avgFits = ();
foreach my $row (@$rows) {
    my $locusId = $row->{locusId};
    my $locusShow = "";
    my $gene = undef;
    if ($locusId ne "") {
        $gene = $genes{$locusId};
        $locusShow = $gene->{sysName} || $gene->{locusId};
    }
    my @row = ( a({-title => "barcode $row->{barcode}"}, &commify($row->{pos})),
                $row->{strand},
                $locusId eq "" ? "" : a({-title => $gene->{desc}, -href => "singleFit.cgi?orgId=$orgId&locusId=$locusId"},
                                        $locusShow),
                $locusId eq "" ? "" : sprintf("%.2f",
                                              ($row->{pos} - $gene->{begin}) / ($gene->{end} - $gene->{begin} + 1))
        );
    @row = map { td($_) } @row;
    my $totalFit = 0; #gather the total for averaging
    my $ind = 0; #gather number of entries 
    foreach my $expName (@expNames) {
        my $fit = $row->{ $expName };
        $totalFit += $fit;
        $ind += 1;
        push @row, td( { -bgcolor => Utils::fitcolor($fit) }, sprintf("%.1f",$fit));
    }
    push @avgFits, $totalFit/$ind;

    push @trows, Tr({-align => 'CENTER', -valign=>'TOP'}, @row);
}

if ($tsv == 1) { # tab delimited values, not a page
    print join("\t", qw{position strand gene fit})."\n";
    my $ind = 0;
    foreach my $row (@$rows) {
        # next unless exists $gene->{x} && exists $gene->{y};
        print join("\t", $row->{pos}, $row->{strand}, $row->{locusId}, $avgFits[$ind])."\n";
        $ind += 1;
    }
    exit 0;
}


if (scalar(@expNames) > 0) {
    # add row for removing items
    my @row = (td(""),td(""),td(""),td(""));
    my $baseURL = "strainTable.cgi?orgId=$orgId&scaffoldId=$scaffoldId&begin=$begin&end=$end";
    foreach my $expName (@expNames) {
        my @otherExps = grep { $_ ne $expName } @expNames;
        my @otherExpSpec = map { "expName=$_" } @otherExps;
        push @row, td( a({ -title => "$expName : $expinfo->{$expName}{expDesc}",
                           -href => join("&", $baseURL, @otherExpSpec) },
                         "remove") );
    }
    push @trows, Tr({-align => 'CENTER', -valign=>'TOP'}, @row);
}



print <<END
<script src="../d3js/d3.min.js"></script>

<P>
<!--<i>x</i> axis: Position
<BR>
<i>y</i> axis: Average Strain Fitness-->

<TABLE width=100% style="border: none;">
<TR class="reset">
<TD valign="top" align="center" style="border: none;"><!-- left column -->

<div id="left"><!-- where SVG goes -->
<div id="loading"><!-- where status text goes -->
Please try another browser if this message remains
</div>
</div>
</TD>
</TR>


</TABLE>
</P>

<script>
var org = "$orgId";
var scaffoldId = "$scaffoldId";
var begin = "$begin";
var end = "$end";
var expName = "$expName";

var xName = "Position (kb)";
var yName = "Average Strain Fitness";


var margin = {top: 20, right: 20, bottom: 50, left: 50},
    width = 850 - margin.left - margin.right,
    height = 500 - margin.top - margin.bottom;

var x = d3.scale.linear()
    .range([0, width]);

var y = d3.scale.linear()
    .range([height, 0]);

var color = d3.scale.category10();
var cValue = function(d) { return d.strand;};

var xAxis = d3.svg.axis()
    .scale(x)
    .orient("bottom");

var yAxis = d3.svg.axis()
    .scale(y)
    .orient("left");

var iSelected = 0; /* for color coding */
var selectColors = [ 'red', 'green', 'blue', 'magenta', 'brown', 'orange', 'darkturquoise' ]; //red for -, green for +

// var svg = d3.select("#left").append("svg")
//     .attr("width",900)
//     .attr("height",500)
//   .append("g")
//     .attr("transform", "translate(" + margin.left + "," + margin.top + ")");
//     // console.log(svg);

var svg = d3.select("#left")
   .append("div")
   .classed("svg-container", true) //container class to make it responsive
   .append("svg")
   //responsive SVG needs these 2 attributes and no width and height attr
   .attr("preserveAspectRatio", "xMinYMin meet")
   .attr("viewBox", "0 0 900 500")
   //class to make it responsive
   .classed("svg-content-responsive", true)
   .append("g")
   .attr("transform", "translate(" + margin.left + "," + margin.top + ")");

d3.select("#loading").html("Fetching data...");
var tsvUrl = "strainTable.cgi?tsv=1&orgId=" + org + "&scaffoldId=" + scaffoldId + "&begin=" + begin + "&end=" + end + "&expName=" + expName;
// console.log(tsvUrl);
d3.tsv(tsvUrl, function(error, data) {
  if (error || data.length == 0) {
      d3.select("#loading").html("Cannot load data from " + tsvUrl + "<BR>Error: " + error);
      return;
  }
  d3.select("#loading").html("Formatting " + data.length + " genes...");
  data.forEach(function(d) {
    d.position = (+d.position)/1000;
    d.fit = +d.fit;
    console.log(d.position, d.fit);
  });

  var extentX = d3.extent(data, function(d) { return d.position; });
  var extentY = d3.extent(data, function(d) { return d.fit; });
  var extentXY = d3.extent([ extentX[0], extentX[1], extentY[0], extentY[1] ]);
  // console.log(extentX, extentY, extentXY);
  x.domain(extentX);//.nice();
  y.domain(extentY).nice();
  // x.domain(extentXY).nice();
  // y.domain(extentXY).nice();

  svg.append("g")
      .attr("class", "x axis")
      .attr("transform", "translate(0," + height + ")")
      .call(xAxis);

  svg.append("text")
      .attr("class", "label")
      .attr("x", 350)
      .attr("y", 500-25)
      .style("text-anchor", "end")
      .text(xName);

  svg.append("g")
      .attr("class", "y axis")
      .call(yAxis);

  svg.append("text")
      .attr("class", "label")
      .attr("transform", "rotate(-90)")
      .attr("x", -80)
      .attr("y", -35)
      .style("text-anchor", "end")
      .text(yName);

  // svg.append("line")
  //      .attr("x1", x(extentXY[0]))
  //      .attr("x2", x(extentXY[1]))
  //      .attr("y1", y(extentXY[0]))
  //      .attr("y2", y(extentXY[1]))
  //      .style("stroke","darkgrey")
  //      .style("stroke-width",1);

  svg.append("line")
       .attr("x1", x(extentXY[0]))
       .attr("x2", x(extentXY[1]))
       .attr("y1", y(0))
       .attr("y2", y(0))
       .style("stroke","darkgrey")
       .style("stroke-width",1);


var tooltip = d3.select("body").append("div")
    .attr("class", "tooltip")
    .style("opacity", 0.0);

  svg.selectAll(".dot")
      .data(data)
    .enter().append("circle")
    .filter(function(d) { return d.gene != "" })
      .attr("class", "dot")
      .attr("r", 5)
      .attr("cx", function(d) { return x(d.position); })
      .attr("cy", function(d) { return y(d.fit); })
      .style("fill", function(d) { 
        if (d.strand == '-'){return "red"} 
        else {return "green"}
        ; })
      .on("mouseover", function(d) {
          tooltip.transition()
               .duration(200)
               .style("opacity", .9);
          tooltip.html(d.gene + ", at position " + (+d.position)+ " on " + d.strand + " strand, with fitness " + (+d.fit).toFixed(1))
               .style("left", (d3.event.pageX + 5) + "px")
               .style("top", (d3.event.pageY - 28) + "px");
      })
      .on("mouseout", function(d) {
          tooltip.transition()
               .duration(500)
               .style("opacity", 0);
      });


  svg.selectAll("dot")
        .data(data)
      .enter().append("circle")
      .filter(function(d) { return d.gene == "" })
        .style("fill", "gray")
        .attr("r", 3.5)
        .attr("cx", function(d) { return x(d.position); })
        .attr("cy", function(d) { return y(d.fit); })
        .on("mouseover", function(d) {
          tooltip.transition()
               .duration(200)
               .style("opacity", .9);
          tooltip.html("position " + (+d.position) + " on " + d.strand + " strand, with fitness " + (+d.fit).toFixed(1))
               .style("left", (d3.event.pageX + 5) + "px")
               .style("top", (d3.event.pageY - 28) + "px");
      })
      .on("mouseout", function(d) {
          tooltip.transition()
               .duration(500)
               .style("opacity", 0);
      });

      // svg.selectAll("text")
      //   .data(data)
      // .enter().append("text")
      // // .filter(function(d) { return d.strand == '-' })
      // .text(function(d) { return d.strand; })
      // .attr("x", function(d) { return x(d.position); })
      // .attr("y", function(d) { return y(d.fit); });

  d3.select("#loading").html("");

});

</script>

END
;
    
print small(table({ cellspacing => 0, cellpadding => 3, }, @trows));

$dbh->disconnect();
Utils::endHtml($cgi);

# i.e., 1234567 => 1,234,567
sub commify($) {
    local $_  = shift;
    1 while s/^(-?\d+)(\d{3})/$1,$2/;
    return $_;
}

