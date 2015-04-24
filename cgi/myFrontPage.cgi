#!/usr/bin/perl -w
#######################################################
## myFrontPage.cgi
##
## Copyright (c) 2015 All Right Reserved by UC Berkeley
##
## Authors:
## Wenjun Shao (wjshao@berkeley.edu) and Morgan Price
#######################################################

use strict;

use CGI qw(:standard Vars);
use CGI::Carp qw(warningsToBrowser fatalsToBrowser);

use lib "../lib";
use Utils;

my $cgi=CGI->new;
my $style = Utils::get_style();

print $cgi->header;
print $cgi->start_html(
    -title =>"Fitness Web Site",
    -style => {-code => $style},
    -author=>'wjshaoATberkeley.edu',
    -meta=>{'copyright'=>'copyright 2015 UC Berkeley'},
#    -BGCOLOR=>'#fffacd'
);

print $cgi->h2("Fitness Web Site");
print $cgi->h6(q(This web site contains <i>unpublished</i> fitness experiments from the Deutschbauer lab, the Arkin lab, and collaborators. Contact <A HREF="mailto:AMDeutschbauer.lbl.gov">Adam Deutschbauer</A> for more information.));

print $cgi->h3("Search by Gene Name");
print $cgi->start_form(
        -name    => 'input',
        -method  => 'GET',
        -action  => 'myFitShow.cgi',
);
print "<P>Choose species: ";
#print $cgi->h6("Note: all species with fitness data are listed here.");

my $dbh = Utils::get_dbh();

# drop down list of species
my %orgLabels = ();
my @orgs = ();
my $orgs = $dbh->selectall_arrayref(qq{SELECT name,genus,species,strain FROM Organism
                                       ORDER BY genus,species,strain }) || die;
foreach my $row (@$orgs) {
    my ($name,$genus,$species,$strain) = @$row;
    push @orgs, $name;
    $orgLabels{$name} = "$genus $species $strain";
}
unshift @orgs, "All";
$orgLabels{"All"} = "All $#orgs genomes";

print $cgi->popup_menu(
    -name    => 'species',
    -values  => \@orgs,
    -labels  => \%orgLabels,
    -default => $orgs[0]
);

print q(<P>Enter gene name: );
print $cgi->textfield(
    -name      => 'gene',
    -size      => 20,
    -maxlength => 100,
);
print $cgi->h6(q(Example: 7022746 (gene locusId) or Shewana3_0001 (gene sysName) or recA (gene name)));
print <<EndOfSubmitOne;
<INPUT TYPE="submit" VALUE="Start fitness lookup">
<INPUT TYPE="reset" VALUE="Clear" onClick="input.gene.value=''">
EndOfSubmitOne

print $cgi->end_form;
print "<BR>\n";

print $cgi->h3(qq(Or Search by Gene Sequence));
print $cgi->start_form(
        -name    => 'input',
        -method  => 'POST',
        -action  => 'mySeqSearch.cgi',
);

print q(<P>Choose query type: );
my @qtype = ("protein","nucleotide");
print $cgi->popup_menu(
    -name    => 'qtype',
    -values  => \@qtype,
    -default => $qtype[0],
);
print $cgi->p(q(Enter query sequence:));
print $cgi->textarea(
    -name  => 'query',
    -value => '',
    -cols  => 70,
    -rows  => 10,
);
print qq(<P>Enter the number of hits to show: );
my @num = (5,10,25,50,100);
print $cgi->popup_menu(
    -name    => 'numHit',
    -values  => \@num,
    -default => $num[2],
);

print <<EndOfSubmitTwo;
<BR><BR>
<INPUT TYPE="submit" VALUE="Start sequence search">
<INPUT TYPE="reset" VALUE="Clear sequence" onClick="input.query.value=''">
EndOfSubmitTwo

print $cgi->end_form;

print $cgi->h6(q(Developed by Wenjun Shao and Morgan Price. Please report any bugs to <A HREF="mailto:funwithwords26@gmail.com">Morgan</A>.));
print $cgi->end_html;

# END
