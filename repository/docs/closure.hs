-- Time-stamp: <2006-08-24 14:25:52 cklin>
-- Copyright 2006 Google Inc. All Rights Reserved.

-- This document describes the algorithm debmarshal uses to compute
-- the dependency transitive closure of a package.  The algorithm is
-- more complicated than standard graph transitive closure because
-- there may be multiple packages that satisfy a single dependency
-- specification.

module Closure where

import Data.List
import Data.Maybe


-- A package is represented by a string in name_version format.  A
-- package description is represented by the Desc type: S represents a
-- single description, and A represents multiple alternatives.  The
-- strings in Desc are just package names.

-- I use a special type for package description so that the type
-- checker can help catch misuse of package descriptions as packages
-- (and vice versa).

data Desc = S String | A [String]

instance Show Desc where
    show (S str)  = str
    show (A strs) = concat (intersperse " | " strs)


-- A made-up package dependency graph with a cycle, an unsatisfiable
-- dependency, and alternative choices.  Each element of 'depends' is
-- a pair of a package and its dependencies.

depends = [("atlantik_1", [S "autoconf"]),
           ("autoconf_2", [A ["console-data", "debconf-doc"], S "cron"]),
           ("console-data_3", [S "atlantik"]),
           ("debconf-doc_4", []),
           ("cron_5", []),
           ("ddd_6", [S "gdb"])]

packages = map fst depends


-- Find packages matching a package description.

match_desc :: Desc -> [String]
match_desc (S s) = filter (isPrefixOf (s ++ "_")) packages
match_desc (A l) = concatMap (match_desc . S) l


-- Compute dependency transitive closure from a package description.
-- The second argument is the list of packages to include into the
-- transitive closure (used for cycle detection).  Since there may be
-- multiple packages satisfying the same package description, the
-- function returns a list of possible closures, each of which is a
-- list of packages.

desc_dep :: Desc -> [String] -> [[String]]
desc_dep d base =
    let candidates = match_desc d
        pkg_dep p = case lookup p depends of
                    Nothing -> []
                    Just ds -> descs_dep ds (p:base)
    in if null (intersect candidates base)
       then concatMap pkg_dep candidates
       else [base]

-- A version of desc_dep that accepts a list of package descriptions
-- and computes a joint transitive closure.  This function is mutually
-- recursive with the desc_dep function.

descs_dep :: [Desc] -> [String] -> [[String]]
descs_dep [] base = [base]
descs_dep (d:ds) base = concatMap (descs_dep ds) (desc_dep d base)

