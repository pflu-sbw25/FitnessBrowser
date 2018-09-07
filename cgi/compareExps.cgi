#!/usr/bin/perl -w
#######################################################
## compareExps.cgi -- interactive scatterplot for two experiments
##
## Copyright (c) 2015 University of California
##
## Authors:
## Morgan Price
#######################################################
#
# Key parameters: orgId, expName1 or query1, expName2 or query2
#	If query1 is set, expName1 is ignored, and similarly for query2
#	Cannot query on both simultaneously, however
# Optional: tsv -- use tsv=1 to fetch the data instead
#	outlier -- list outlying genes (xlow, xhigh, ylow, or yhigh)
#       with minabs -- minimum |abs| on selected axis.
# help -- 1 if on help/tutorial mode

use strict;
use CGI qw(:standard Vars -nosticky);
use CGI::Carp qw(warningsToBrowser fatalsToBrowser);
use DBI;

use lib "../lib";
use Utils;

my $cgi=CGI->new;
print $cgi->header;

my $orgId = $cgi->param('orgId');
my $expName1 = $cgi->param('expName1') || "";
$expName1 =~ s/^[ \t]+//;
$expName1 =~ s/[ \t\r\n]+$//;
my $expName2 = $cgi->param('expName2') || "";
$expName2 =~ s/^[ \t]+//;
$expName2 =~ s/[ \t\r\n]+$//;
my $query1 = $cgi->param('query1') || "";
$query1 =~ s/^[ \t]+//;
$query1 =~ s/[ \t\r\n]+$//;
my $query2 = $cgi->param('query2') || "";
$query2 =~ s/^[ \t]+//;
$query2 =~ s/[ \t\r\n]+$//;
my $tsv = $cgi->param('tsv') ? 1 : 0;
my $help = $cgi->param('help') || "";
my $outlier = $cgi->param('outlier');
die "Must specify orgId" unless defined $orgId && $orgId ne "";
die "Must specify expName1 or query1"
    if $expName1 eq "" && $query1 eq "";
die "Must specify expName2 or query2"
    if $expName2 eq "" && $query2 eq "";
die "Cannot query both 1 and 2" if $query1 ne "" && $query2 ne "";

my $dbh = Utils::get_dbh();
my $orginfo = Utils::orginfo($dbh);
Utils::fail($cgi, "Unknown organism: $orgId") unless exists $orginfo->{$orgId};

my @expCand = ();
my $choosing = undef;
if (defined $query1 && $query1 ne "") {
    my @exps = @{ Utils::matching_exps($dbh,$orgId,$query1) };
    Utils::fail($cgi, qq{No experiment matching "$query1"}) if @exps == 0;
    @exps = grep { $_->{expName} ne $expName2 } @exps if @exps > 1;
    if (@exps == 1) {
	$expName1 = $exps[0]{expName};
    } else {
	@expCand = @exps;
	$choosing = 1;
    }
} elsif (defined $query2 && $query2 ne "") {
    my @exps = @{ Utils::matching_exps($dbh,$orgId,$query2) };
    Utils::fail($cgi, qq{No experiment matching "$query2"}) if @exps == 0;
    @exps = grep { $_->{expName} ne $expName1 } @exps if @exps > 1;
    if (@exps == 1) {
	$expName2 = $exps[0]{expName};
    } else {
	@expCand = @exps;
	$choosing = 2;
    }
}

if (scalar(@expCand) > 0) {
    die "Cannot use tsv mode with queries" if $tsv;
    # show table of these experiments
    my $expNameConst = $choosing == 1 ? $expName2 : $expName1;
    my $expConst = $dbh->selectrow_hashref("SELECT * from Experiment WHERE orgId = ? AND expName = ?",
					   {}, $orgId, $expNameConst);
    die "Unknown experiment: $expNameConst" unless exists $expConst->{expName};
    my $notChoosing = $choosing == 1 ? 2 : 1;

    my @trows = ();
    my @headings = qw{&nbsp; name group condition description};
    push @trows, $cgi->Tr({-valign => 'top', -align => 'center'}, $cgi->th(\@headings));
    my $isFirst = 1;
    foreach my $exp (@expCand) {
	my $checked = $isFirst ? "CHECKED" : "";
	push @trows, $cgi->Tr({-valign => 'top', -align => 'left'},
			      $cgi->td([ qq{<input type="radio" name="expName$choosing" value="$exp->{expName}" $checked >},
					 $cgi->a({href => "exp.cgi?orgId=$orgId&expName=$exp->{expName}"}, $exp->{expName}),
					 $exp->{expGroup}, $exp->{condition_1}, $exp->{expDesc} ]));
	$isFirst = 0;
    }

  my $start = Utils::start_page("Select experiment to compare to");
    print $start, '<div id="ntcontent">',
	p("Select an experiment to compare to ",
	  a( { href => "exp.cgi?orgId=$orgId&expName=$expNameConst" }, $expConst->{expName} ),
	  "($expConst->{expDescLong})"),
	start_form(-name => 'input', -method => 'GET', -action => 'compareExps.cgi'),
	hidden('orgId', $orgId),
	hidden("expName$notChoosing", $expNameConst),
	table( {cellpadding => 3, cellspacing => 0}, @trows),
	submit('Go'),
	end_form;
    Utils::endHtml($cgi);
}

# else

my $exp1 = $dbh->selectrow_hashref("SELECT * from Experiment WHERE orgId = ? AND expName = ?",
				   {}, $orgId, $expName1);
die "Unknown experiment: $expName1" unless exists $exp1->{expName};

my $exp2 = $dbh->selectrow_hashref("SELECT * from Experiment WHERE orgId = ? AND expName = ?",
				   {}, $orgId, $expName2);
die "Unknown experiment: $expName2" unless exists $exp2->{expName};

my $genes; # locusId => genes => attribute, with additional values x, y, tx, ty

if ($tsv || $outlier) {
    # fetch the data
    $genes = $dbh->selectall_hashref("SELECT * FROM Gene where orgId = ?", "locusId", {}, $orgId);
    die "No genes" unless scalar(keys %$genes) > 0;
    # these tables are ordered by experiment, so faster than using GeneFitness
    # (Quoting is necessary in case orgId has - in it.)
    my $fit = $dbh->selectall_arrayref("SELECT * FROM 'FitByExp_${orgId}' WHERE expName IN (?,?)",
				       { Slice => {} }, $expName1, $expName2);
    my $found1 = 0;
    my $found2 = 0;
    foreach my $row (@$fit) {
	my $locusId = $row->{locusId};
	die "Unrecognized locus $locusId for org $orgId" unless exists $genes->{$locusId};
	my $gene = $genes->{$locusId};
	if ($row->{expName} eq $expName1) {
	    $gene->{x} = $row->{fit};
	    $gene->{tx} = $row->{t};
	    $found1 = 1;
	}
	if ($row->{expName} eq $expName2) {
	    $gene->{y} = $row->{fit};
	    $gene->{ty} = $row->{t};
	    $found2 = 1;
	}
    }
    Utils::fail($cgi, "No fitness values for $expName1 in $orgId") unless $found1 > 0;
    Utils::fail($cgi, "No fitness values for $expName2 in $orgId") unless $found2 > 0;
}

if ($tsv) { # tab delimited values, not a page
    print join("\t", qw{locusId sysName gene desc x tx y ty})."\n";
    while (my ($locusId,$gene) = each %$genes) {
	next unless exists $gene->{x} && exists $gene->{y};
	print join("\t", $locusId, $gene->{sysName}, $gene->{gene},
                   $gene->{desc},
		   $gene->{x}, $gene->{tx}, $gene->{y}, $gene->{ty})."\n";
    }
    exit 0;
} elsif ($outlier) { # table of outlying genes
    my $minabs = $cgi->param('minabs');
    $minabs = 2 unless defined $minabs && $minabs > 0;

    my $outlierCode = "";
    if ($outlier eq "lowx") {
	$outlierCode = "exp1 &lt; -$minabs and exp2 &gt; -1.0";
    } elsif ($outlier eq "lowy") {
	$outlierCode = "exp1 &gt; -1.0 and exp2 &lt; -$minabs";
    } elsif ($outlier eq "highx") {
	$outlierCode = "exp1 &gt; $minabs and exp2 &lt; 1.0";
    } elsif ($outlier eq "highy") {
	$outlierCode = "exp1 &lt; 1.0 and exp2 &gt; $minabs";
    } else {
	die "Unrecognized code for outlier";
    }
    # &#124; is |
    $outlierCode .= " and &#124;<i>x</i>-<i>y</i>&#124; &gt; 1.0" if $minabs < 2;
    $outlierCode =~ s!exp1!<i>x</i>!g;
    $outlierCode =~ s!exp2!<i>y</i>!g;

    my @genesShow = ();
    while (my ($locusId,$gene) = each %$genes) {
	next unless exists $gene->{x} && exists $gene->{y};
	my $x = $gene->{x};
	my $y = $gene->{y};
	my $diff = abs($x-$y);
	push @genesShow, $gene
	    if $diff > 1
	    && (($outlier eq "lowx" && $x < -$minabs && $y > -1)
		|| ($outlier eq "lowy" && $y < -$minabs && $x > -1)
		|| ($outlier eq "highx" && $x > $minabs && $y < 1)
		|| ($outlier eq "highy" && $y > $minabs && $x < 1));

    }

    if ($outlier eq "lowx") {
	@genesShow = sort { $a->{x} <=> $b->{x} } @genesShow;
    } elsif ($outlier eq "lowy") {
	@genesShow = sort { $a->{y} <=> $b->{y} } @genesShow;
    } elsif ($outlier eq "highx") {
	@genesShow = sort { $b->{x} <=> $a->{x} } @genesShow;
    } elsif ($outlier eq "highy") {
	@genesShow = sort { $b->{y} <=> $a->{y} } @genesShow;
    }

my $start = Utils::start_page("Outlier genes from $orginfo->{$orgId}{genome}");
    
    print $start, '<div id="ntcontent">',
	h2("Outlier genes from $orginfo->{$orgId}{genome}");

if ($help) {
    print qq[<div class="helpbox">
    <b><u>About this page:</u></b><BR><ul>
    <li>View genes that have different fitness in the two experiments: they are important for fitness in $exp2->{expDesc} but not in $exp1->{expDesc}.</li>
    <li>The most important genes in $exp2->{expDesc} are shown first.
    <li>To get to this page, use the outlier button when viewing the scatterplot comparing two experiments.</li> 
    <li>You can also view a heatmap of the top genes (link at bottom).</li>
    </ul></div>];
  }


	print h3($outlierCode),
	p(qq{<i>x</i> is fitness in <A HREF="exp.cgi?orgId=$orgId&expName=$expName1">$expName1</A>: $exp1->{expDescLong} }
	  . "<BR>"
	  . qq{<i>y</i> is fitness in <A HREF="exp.cgi?orgId=$orgId&expName=$expName2">$expName2</A>: $exp2->{expDescLong} }),
	p(scalar(@genesShow) . " genes found");
    if (@genesShow > 0) {
	my @trows = ();
	my @headings = qw{gene name description x y};
	push @trows, $cgi->Tr({-align=>'center',-valign=>'top'}, $cgi->th(\@headings));
        my $GroupCond1 = "expGroup=$exp1->{expGroup}&condition1=$exp1->{condition_1}";
        my $GroupCond2 = "expGroup=$exp2->{expGroup}&condition1=$exp2->{condition_1}";
	foreach my $gene (@genesShow) {
	    my $colorX = Utils::fitcolor($gene->{x});
	    my $colorY = Utils::fitcolor($gene->{y});
	    my $x = sprintf("%.1f",$gene->{x});
	    my $y = sprintf("%.1f",$gene->{y});
	    my $tx = sprintf("%.1f",$gene->{tx});
	    my $ty = sprintf("%.1f",$gene->{ty});
            my $orthFitBase = "orthFit.cgi?orgId=$orgId&locusId=$gene->{locusId}";

	    push @trows, $cgi->Tr({-align=>'left',-valign=>'top'},
		                  $cgi->td(Utils::gene_link($dbh, $gene, "name", "myFitShow.cgi")),
				  $cgi->td($gene->{gene}),
                                  $cgi->td(Utils::gene_link($dbh, $gene, "desc", "domains.cgi")),
				  $cgi->td({ -bgcolor => Utils::fitcolor($gene->{x}) },
					   $cgi->a({title => sprintf("t = %.1f. Click for conservation.", $gene->{tx}),
                                                    href => "$orthFitBase&$GroupCond1" },
						   sprintf("%.1f", $gene->{x}))),
				  $cgi->td({ -bgcolor => Utils::fitcolor($gene->{y}) },
					   $cgi->a({title => sprintf("t = %.1f. Click for conservation", $gene->{ty}),
                                                    href => "$orthFitBase&$GroupCond2" },
						   sprintf("%.1f", $gene->{y}))) );
	}
	my $limitString = "";
	if (@genesShow > 20) {
	    @genesShow = @genesShow[0..19];
	    $limitString = "top 20";
	}
	my $heatURL = "genesFit.cgi?orgId=$orgId&" . join("&", map { "locusId=" . $_->{locusId} } @genesShow);

	print
	    table({cellpadding=>3, cellspacing=>0}, @trows),
	    p(a({href => $heatURL}, "Heatmap for $limitString genes"));
	    
    }
    print p(a({href => "compareExps.cgi?orgId=$orgId&expName1=$expName1&expName2=$expName2"},"Show scatterplot"));

    $dbh->disconnect();
    Utils::endHtml($cgi);
}
# else interactive scatterplot
$dbh->disconnect();

my $title = "Compare Experiments for $orginfo->{$orgId}{genome}";
my $start = Utils::start_page("$title");
my $helptext = "";
if ($help) {
  $helptext = qq[<div class="helpbox">
    <b><u>About this page:</u></b><BR><ul>
    <li>Each point shows the fitness of a gene in the two experiments</A>
    <li>To get to this page, search for any experiment and add another experiment to compare to.</li> 
    <li>Hover on a point to see what gene it is, or click to add the gene to the table.</li>
    <li>Or make a table of all the genes that are outliers, i.e., use "Low y" to list genes that are only important in $exp2->{expDesc}.</li>
    </ul></div>];
}

my $bottom = p("Download", 
               a( { -href => "createFitData.cgi?orgId=$orgId&expName=$expName1&expName=$expName2" },
                  "fitness data for these experiments"));

print <<END
$start
<script src="../d3js/d3.min.js"></script>
<body style="padding-left: 1%">
<div id="ntcontent">

<H2>$title</H2>

<P>
<i>x</i> axis: Fitness in <A HREF="exp.cgi?orgId=$orgId&expName=$expName1">$expName1</A>, $exp1->{expDescLong}
<BR>
<i>y</i> axis: Fitness in <A HREF="exp.cgi?orgId=$orgId&expName=$expName2">$expName2</A>, $exp2->{expDescLong}

$helptext

<TABLE width=100% style="border: none;">
<TR class="reset">
<TD valign="top" align="left" style="border: none;"><!-- left column -->

<div id="left"><!-- where SVG goes -->
<div id="loading"><!-- where status text goes -->
Please try another browser if this message remains
</div>
</div>
</TD>
<TD valign="top" align="left" style="border: none;"><!-- right column -->
<p>

<form method="get" action="compareExps.cgi" enctype="multipart/form-data" name="input">
<input type="hidden" name="orgId" value="$orgId" />
<input type="hidden" name="expName2" value="$expName2" />
Change x axis: <input type="text" name="query1"  size="20" maxlength="100" />
<button type='submit'>Go</button>
</form>

<form method="get" action="compareExps.cgi" enctype="multipart/form-data" name="input">
<input type="hidden" name="orgId" value="$orgId" />
<input type="hidden" name="expName1" value="$expName1" />
Change y axis: <input type="text" name="query2"  size="20" maxlength="100" />
<button type='submit'>Go</button>
</form>

<form method="get" action="compareExps.cgi" enctype="multipart/form-data" name="input">
<input type="hidden" name="orgId" value="$orgId" />
<input type="hidden" name="expName1" value="$expName2" />
<input type="hidden" name="expName2" value="$expName1" />
<input type="submit" name="flip" value="Flip axes" />
</form>
</p>

  <P><b>Click on genes to add them to the table:</b>

<TABLE id="genesel" cellspacing=0 cellpadding=3 >
<tr><th>gene</th><th>name</th><th>description</th><th>x</th><th>y</th><th>&nbsp;</th></tr>
</TABLE>
</P>
<P>
<A href="#" onclick="geneList()">Heatmap for selected genes</A>

<P>
<form method="get" action="compareExps.cgi" enctype="multipart/form-data" name="input">
<input type="hidden" name="orgId" value="$orgId" />
<input type="hidden" name="expName1" value="$expName1" />
<input type="hidden" name="expName2" value="$expName2" />
<b>Or see outliers with
<select name="outlier">
   <option value="lowx">Low <i>x</i></option>
   <option value="lowy">Low <i>y</i></option>
   <option value="highx">High <i>x</i></option>
   <option value="highy">High <i>y</i></option>
</select>
and |fit| &gt; <select name="minabs" style="width: 60px;">
    <option value="1" selected>1.0 </option>
    <option value="1.5">1.5</option>
    <option value="2">2.0</option>
    <option value="2.5">2.5</option>
    <option value="3">3.0</option>
</select></b>
<input type="submit" name="submit" value="Go">
</form>

</TD></TR></TABLE>
</P>

<script>
var org = "$orgId";
var xName = "$expName1";
var yName = "$expName2";
var xDesc = "$exp1->{expDesc}";
var yDesc = "$exp2->{expDesc}";

var margin = {top: 20, right: 20, bottom: 50, left: 50},
    width = 500 - margin.left - margin.right,
    height = 500 - margin.top - margin.bottom;

var x = d3.scale.linear()
    .range([0, width]);

var y = d3.scale.linear()
    .range([height, 0]);

//var color = d3.scale.category10();

var xAxis = d3.svg.axis()
    .scale(x)
    .orient("bottom");

var yAxis = d3.svg.axis()
    .scale(y)
    .orient("left");

var iSelected = 0; /* for color coding */
var selectColors = [ 'red', 'green', 'blue', 'magenta', 'brown', 'orange', 'darkturquoise' ];

var svg = d3.select("#left").append("svg")
    .attr("width",500)
    .attr("height",500)
  .append("g")
    .attr("transform", "translate(" + margin.left + "," + margin.top + ")");

d3.select("#loading").html("Fetching data...");
var tsvUrl = "compareExps.cgi?tsv=1&orgId=" + org + "&expName1=" + xName + "&expName2=" + yName;
d3.tsv(tsvUrl, function(error, data) {
  if (error || data.length == 0) {
      d3.select("#loading").html("Cannot load data from " + tsvUrl + "<BR>Error: " + error);
      return;
  }
  d3.select("#loading").html("Formatting " + data.length + " genes...");
  data.forEach(function(d) {
    d.x = +d.x;
    d.y = +d.y;
    d.tx = +d.tx;
    d.ty = +d.ty;
  });

  var extentX = d3.extent(data, function(d) { return d.x; });
  var extentY = d3.extent(data, function(d) { return d.y; });
  var extentXY = d3.extent([ extentX[0], extentX[1], extentY[0], extentY[1] ]);
  x.domain(extentXY).nice();
  y.domain(extentXY).nice();

  svg.append("g")
      .attr("class", "x axis")
      .attr("transform", "translate(0," + height + ")")
      .call(xAxis);

  svg.append("text")
      .attr("class", "label")
      .attr("x", 350)
      .attr("y", 500-25)
      .style("text-anchor", "end")
      .text(xDesc);

  svg.append("g")
      .attr("class", "y axis")
      .call(yAxis);

  svg.append("text")
      .attr("class", "label")
      .attr("transform", "rotate(-90)")
      .attr("x", -80)
      .attr("y", -30)
      .style("text-anchor", "end")
      .text(yDesc);

  
  svg.append("line")
       .attr("x1", x(extentXY[0]))
       .attr("x2", x(extentXY[1]))
       .attr("y1", y(extentXY[0]))
       .attr("y2", y(extentXY[1]))
       .style("stroke","darkgrey")
       .style("stroke-width",1);

  svg.append("line")
       .attr("x1", x(extentXY[0]))
       .attr("x2", x(extentXY[1]))
       .attr("y1", y(0))
       .attr("y2", y(0))
       .style("stroke","darkgrey")
       .style("stroke-width",1);

  svg.append("line")
       .attr("x1", x(0))
       .attr("x2", x(0))
       .attr("y1", y(extentXY[0]))
       .attr("y2", y(extentXY[1]))
       .style("stroke","darkgrey")
       .style("stroke-width",1);

var tooltip = d3.select("body").append("div")
    .attr("class", "tooltip")
    .style("opacity", 0.0);

  svg.selectAll(".dot")
      .data(data)
    .enter().append("circle")
      .attr("class", "dot")
      .attr("r", 3)
      .attr("cx", function(d) { return x(d.x); })
      .attr("cy", function(d) { return y(d.y); })
      .on("click", dotClick)
      .on("mouseover", function(d) {
          tooltip.transition()
               .duration(200)
               .style("opacity", .9);
          tooltip.html(d.gene + " (" + (d.sysName||d.locusId) + "): " + d.desc + "<br/> (" + (+d.x).toFixed(1) 
          + ", " + (+d.y).toFixed(1)  + ")")
               .style("left", (d3.event.pageX + 5) + "px")
               .style("top", (d3.event.pageY - 28) + "px");
      })
      .on("mouseout", function(d) {
          tooltip.transition()
               .duration(500)
               .style("opacity", 0);
      });
  // .style("fill", function(d) { return color(d.species); });

  d3.select("#loading").html("");

  /*
  var legend = svg.selectAll(".legend")
      .data(color.domain())
    .enter().append("g")
      .attr("class", "legend")
      .attr("transform", function(d, i) { return "translate(0," + i * 20 + ")"; });
  legend.append("rect").attr("x", width - 18).attr("width", 18).attr("height", 18).style("fill", color);
  legend.append("text").attr("x", width - 24).attr("y", 9).attr("dy", ".35em").style("text-anchor", "end").text(function(d) { return d; });
  */
});

// If a dot is clicked, and it is not already highlighted, then:
// its isset attribute is set to "1"
// its color is set using selectColors[] and iSelected++
// its r (radius) is set to 5
// a row is added to the table, and the row's locusId attribute is set

function dotClick(d) {
    var col = selectColors[(iSelected++) % selectColors.length];
    if (this.getAttribute("isset") !== "1") {
      this.setAttribute("isset", "1");
      d3.select(this).style("fill",col).attr("r",5);
      columns = [ d.sysName, d.gene, d.desc ];
      var tr = d3.select("#genesel").append("tr").attr("class","reset2").attr("valign","middle").style("color", col);
      var showId = d.sysName === "" ? d.locusId : d.sysName;
      var URL = "myFitShow.cgi?orgId=" + org + "&gene=" + d.locusId;
      var beginHref = "<A target='_blank' style='color: " + col + "' HREF='" + URL + "'>";
      tr.append("td").attr("class","locusId").attr("locusId",d.locusId).html(beginHref + showId + "</A>");
      tr.append("td").html(d.gene);
      tr.append("td").html(d.desc);
      var hrefX = "strainTable.cgi?orgId=" + org + "&expName=" + xName + "&locusId=" + d.locusId;
      var hrefY = "strainTable.cgi?orgId=" + org + "&expName=" + yName + "&locusId=" + d.locusId;
      tr.append("td").html("<A TITLE='t = " + d.tx.toFixed(1) + "' HREF='" + hrefX + "'>" + d.x.toFixed(1) + "</A>");
      tr.append("td").html("<A TITLE='t = " + d.ty.toFixed(1) + "' HREF='" + hrefY + "'>" + d.y.toFixed(1) + "</A>");
      tr.append("td").html("<button type='button' onclick='removeRow(this)'>remove</button>");
      tr.attr("locusId", d.locusId);
  }
}

// When the remove button is hit, remove the row and set the dot to have:
// isset = 0, r = 3, color = black
function removeRow(a) {
    row = a.parentNode.parentNode; // button to td to row
    // just using row.locusId does not work, not sure why not
    locusId = row.getAttribute("locusId");
    row.parentNode.removeChild(row);
    // and uncolor the point
    d3.selectAll(".dot")
      .filter(function(d,i) { return d.locusId == locusId })
        .style("fill","black")
        .attr("r",3)
        .attr("isset", 0);
}

function geneList() {
    var tds = document.getElementsByClassName("locusId");
    if (tds.length > 0) {
	var URL;
	if (tds.length == 1) {
	    URL = "myFitShow.cgi?orgId=" + org + "&gene=" + tds[0].getAttribute("locusId");
	} else {
            var i;
	    URL = "genesFit.cgi?orgId=" + org;
            for (i = 0; i < tds.length; i++ ) {
                URL += "&locusId=" + tds[i].getAttribute("locusId");
            }
	}
        window.open(URL);
   }
}

</script>

</div>
$bottom
</body>
</html>
END
;
