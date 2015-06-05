#!/usr/bin/perl -w
#######################################################
## exps.cgi -- search for experiments, or list all in one organism
##
## Copyright (c) 2015 University of California
##
## Authors:
## Morgan Price and Victoria Lo
#######################################################
#
# Key parameters: orgId and query, for which organism and to look up experiments
#	At least one must be meaningful (present and not empty)
# OR, specify expGroup AND condition1. In this set up, condition1 may be empty,
#	but it must still be specified (and is used to restrict the results).
# OR, specify orgId AND expGroup without condition1.

use strict;
use CGI qw(:standard Vars);
use CGI::Carp qw(warningsToBrowser fatalsToBrowser);
use DBI;

use lib "../lib";
use Utils;

my $cgi=CGI->new;

my $orgId = $cgi->param('orgId');
$orgId = "" if !defined $orgId;

my $expSpec = $cgi->param('query');
$expSpec = "" if !defined $expSpec;
my $expGroup = $cgi->param('expGroup');
my $condition1 = $cgi->param('condition1');

# Sanitize all input
$orgId, $expSpec, $expGroup, $condition1 =~ s/ +$//;
$orgId, $expSpec, $expGroup, $condition1 =~ s/^ +$//;
$orgId, $expSpec, $expGroup, $condition1 =~ s/[\'\"\n\r\;\\]//g; #'

my $dbh = Utils::get_dbh();

# Make sure both parameters are safe
my $orginfo = Utils::orginfo($dbh);
Utils::fail($cgi, "Unknown organism: $orgId") unless $orgId eq "" || exists $orginfo->{$orgId};

$expSpec = "" if $cgi->param("All experiments");

my $exps;
# Redirect to orgGroup.cgi if displaying all exp from one organism
if ($orgId ne "" && !defined $expGroup && ($cgi->param("All experiments") || $cgi->param("query") == "")) {
    print redirect(-url=>"org.cgi?orgId=$orgId");
} elsif (defined $expGroup && defined $orgId && !defined $condition1){
    # $exps = Utils::matching_exps_strict($dbh, $orgId, $expSpec, $expGroup);
    $exps = $dbh->selectall_arrayref(qq{SELECT * from Experiment WHERE expGroup = ? AND orgId = ?},
            { Slice => {} },
            $expGroup, $orgId);
} elsif (defined $expGroup && defined $condition1) {
    $exps = $dbh->selectall_arrayref(qq{SELECT * from Experiment WHERE expGroup = ? AND condition_1 = ?},
				    { Slice => {} },
				    $expGroup, $condition1);
    Utils::fail($cgi, "No experiments for specified group and condition") if scalar(@$exps) == 0;
} elsif ($orgId eq "" && $expSpec eq "") {
    Utils::fail($cgi, "Cannot show all experiments: please specify organism and/or condition");
} else {
    $exps = Utils::matching_exps($dbh, $orgId, $expSpec);
}

my $style = Utils::get_style();
print $cgi->header;

print $cgi->start_html(
    -title =>"Experiments for $expSpec",
    -style => {-code => $style},
    -author=>'Morgan Price',
    -meta=>{'copyright'=>'copyright 2015 UC Berkeley'},
);

if (@$exps == 0) {
   print $cgi->h3(qq{No experiment found matching "$expSpec"});
} else {
  my $heading = "Experiments";
  $heading .= " in $orginfo->{$orgId}{genome}" if $orgId ne "";
  $heading .= qq{ matching "$expSpec"} if $expSpec ne "";
  print $cgi->h2($heading);
  my @trows = ();
  push @trows, $cgi->Tr({-valign => "top"}, $cgi->th([ 'Organism', 'Name', 'Group', 'Condition', 'Description' ]));
  foreach my $row (@$exps) {
      push @trows, $cgi->Tr({-valign => "top"},
             $cgi->td([ $orginfo->{$row->{orgId}}{genome},
	              $cgi->a({href => "exp.cgi?orgId=$row->{orgId}&expName=$row->{expName}"}, $row->{expName}),
		      $row->{expGroup}, $row->{condition_1}, $row->{expDesc} ]));
  }
  print table({cellspacing => 0, cellpadding => 3}, @trows);
  my $exp1 = $exps->[0];
  if ($exp1->{expGroup} ne ""
      && ($expSpec ne "" || (defined $expGroup && defined $condition1))) {
      print p(a( { -href => "orthCond.cgi?expGroup=$exp1->{expGroup}&condition1=$exp1->{condition_1}" },
		 "Specific phenotypes for $exp1->{expGroup} $exp1->{condition_1} across organisms"));
  }
}

$dbh->disconnect();
Utils::endHtml($cgi);
