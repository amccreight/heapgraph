Analysis of Firefox cycle collector and garbage collector heap dumps
====================================================================


Understanding a Firefox shutdown leak
-------------------------------------

1. In a debug build, a shutdown leak will cause the browser to display a BloatView, listing objects that leak. You will want to examine that to see what exactly is leaking. If it is just a few objects, the easiest thing may be to look at code you have modified related to those things. If code inspection fails, or you are leaking an nsDocument or nsGlobalWindow, then ...