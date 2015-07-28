<h1> GRAM Software Release Process</h1>

1. Introduction

GRAM is a body of software to present a GENI Aggregate Manager (AM) API front-end to a set of Openstack managed cloud resources. GRAM is the underlying software for the OpenGENI racks.

The GRAM software is maintained in this GitHub repository(https://github.com/GENI-NSF/gram).

2. Standard Development

It is expected that developers will work on branches off the git develop branch.

The standard process for making a change to the GRAM git repository:

* Create a ticket in GitHub for the feature to be added or bug to be fixed. (Here, #XXX).
* Create a branch for developing the fix.  
    git checkout develop  
    git checkout -b tktXXX_new_feature
* Install the fix on a test machine and test
* Edit the CHANGES file to include the new feature and reference the associated ticket for the next release  
    Add 'New Feature' (#XXX).
* Commit the new feature and merge back into develop  
    git add -A  
    git commit -m"Add feature for ticket XXX"  
    git checkout develop  
    git merge tktXXX_new_feature  
* Delete feature branch  
    git branch -d tktXXX_new_feature
* Close ticket XXX

3. Release Process

Release types


4. Distribution

   Notifications
   Updates

