#!/usr/bin/perl
#######################################################
## Utils.pm
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

sub excute_db($;$);
sub get_style();
sub fail($;$);
sub formatFASTA($;$);
sub crc64($);
sub get_color($);
sub get_dbh(); # open the sqlite db and return the resulting database handle
sub blast_db();
sub tmp_dir();

#--------------------------------------------------------

sub get_style() {
    my $style = <<"EOT";
    body {
        font-family: verdana, arial, sans-serif;
        bgcolor: "#fffacd";
        padding-left: 5%;
    }
    H2 {
        color: red;
        border-bottom: 1pt solid;
    }
    H4 {
        color: blue;
    }
    p {
        color: darkblue;
        font-variant: small-caps;
        font-weight: bold;
    }
    table {
        border: darkblue 1pt solid;
    }
    th,td {
        border: blue 1pt dashed;
    }
EOT
    return $style;
}

sub execute_db($;$) {
    my ($dbh, $stmt) = @_;
    my $sth = $dbh->prepare( $stmt );
    my $rv = $sth->execute() or die $DBI::errstr;
    print $DBI::errstr if($rv < 0);
    return $sth;
}

sub fail($;$) {
    my ($cgi, $notice) = @_;
    print $cgi->h3(qq(<font color="red">WARNING</font> $notice));
    print $cgi->h4(qq(<a href="myFrontPage.cgi">Go back to front page</a>));
    print $cgi->end_html;
    exit;
}

sub endHtml($) {
    my ($cgi) = @_;
    print $cgi->h4(qq(<a href="myFrontPage.cgi">Go back to front page</a>));
    print $cgi->end_html;
    exit 0;
}

#--------------------------------------------------------

sub formatFASTA($;$)
{
    my ($title, $sequence) = @_;
    return undef unless ($sequence);
    my $s = qq/>$title\n/;
    my @whole = $sequence =~ /.{1,60}/g;
    my $line = join "\n", @whole;
    return $s."$line\n";
}

#--------------------------------------------------------

sub get_color($) {
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

    my $string=sprintf (" #%2.2X%2.2X%2.2X\n",$red,$green,$blue);
    return ($string);
}

sub get_dbh() {
    my $database = "../cgi_data/feba.db";
    return DBI->connect("dbi:SQLite:dbname=$database","","",{ RaiseError => 1 }) || die $DBI::errostr;
}

sub blast_db() {
    return "../cgi_data/aaseqs";
}

sub tmp_dir() {
    return "../tmp";
}

#END 


return 1;

