<h1> GRAM Software Release Process</h1>

1. <b>Introduction</b>

GRAM is a body of software to present a GENI Aggregate Manager (AM) API front-end to a set of Openstack managed cloud resources. GRAM is the underlying software for the OpenGENI racks.

The GRAM software is maintained in this GitHub repository(https://github.com/GENI-NSF/gram).

2. <b>Standard Development</b>

It is expected that developers will work on branches off the git develop branch. The master branch contains the configuration managed baseline.

The standard process for making a change to the GRAM git repository:

* Create a ticket in GitHub for the feature to be added or bug to be fixed. (Here, #XXX).
* Create a branch for developing the fix.  
    git checkout develop  
    git checkout -b tktXXX_new_feature
* Install the fix on a test machine and test
* Edit the CHANGES file to include the new feature and reference the associated ticket for the next release  
    Add 'New Feature' (#XXX).
    <i>Make sure to document any configuration variables (config.json, config.py) added.</i>   
* Commit the new feature and merge back into develop  
    git add -A  
    git commit -m"Add feature for ticket XXX"  
    git checkout develop  
    git merge tktXXX_new_feature  
* Delete feature branch  
    git branch -d tktXXX_new_feature
* Close ticket XXX

3. <b>Release Process</b>

Major releases require changes to the underlying installation or architecture. These are numbered X.0 where X is the next major release.

Minor releases do not change the underlying installation or architecture (that is, only GRAM software is changed, but no change to libraries, OpenStack, switch configuration, etc.). These are numbered X.Y where X is the current major release and Y is the next minor release within that major release.

The procedure for creating a new GRAM release:

* Create a ticket to document the release including any special installation instructions (changes to configuration or database or network, e.g.).
* Create a branch for branch X.Y  
    git checkout develop  
    git checkout -b release-X.Y
* Verify that all changes in git match changes documented in CHANGES, and update CHANGES as necessary. 
* Close tickets that are included in the release but not closed.
* Set the src/GRAMVERSION file to reflect the next release number  
    Tag vX.Y  
* Tag the new release  
    git tag -a -m "GRAM X.Y" vX.Y release-X.Y     
    git push --tags origin    
* Create update packages  
    **Need help here**  
* Install and test update packages.  
    <i>There should be a test machine with the previous release installed on it from which we can test the upgrade and new features. </i>
* Close the ticket.  
* Merge the release branch into master and develop  
   git fetch origin -p  
   git checkout master  
   git merge origin/master  
   git merge --no-ff release-X.Y  
   git push origin master  
   git checkout develop  
   git merge origin/develop  
   git merge --no-ff release-X.Y  
   git push origin develop  
* Delete the release branch  
    git branch -d release-X.Y  

4. <b>Distribution</b>

The GRAM releases may be installed at the discretion and convenience of the rack owner. We need to notify the owners of the existence of the new release, the features and fixes contained in the release, the procedure for upgrading (so they can assess risk).
* Send a note to all GRAM rack owners about the new release telling them to get in touch if they are interested in upgrading.
* Send the upgrade package and install/upgrade instructions to rack owner that is interested
* It is the responsibility of the rack owner (not the GRAM development team) to notify users of outages due to the upgrade.
* Support the rack team with any issues in testing or installation as needed.
* After upgrade, have rack owner send the most recent config.json and GRAMVERSION files for reference.
* Maintain a record of which GRAM installations have which Software release and current config.json file.
