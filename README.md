# DAEFix

Repairs rigged mesh COLLADA .dae files exported from MAXON Cinema 4D so that they are compatible with Second Life mesh upload.

## Usage
```
python daefix.py [-h] infile [outfile]
```

### What is this for?

COLLADA format expects node tags with `id` attributes. Cinema 4D saves the names of scene elements into node `name` attributes, and replaces id by some generated unique id value, regardless of the name. This is not the same way Blender handles it, or how Second Life's mesh uploader expects it to be. Essentially, all this script does is re-map the id attributes of joints to their name attribute values.

However, there are some additional requirements for making rigged mesh attachments / animesh-compatible models for Second Life in Cinema 4D.


## Modeling Guide

Cinema 4D exports COLLADA .dae files that have partial compatibility with Second Life. Non-rigged models are for the most part completely compatible out of the box, but rigged meshes need some persuasion. The avatar skeleton needs to be of a compatible structure (e.g. [Bento](http://wiki.secondlife.com/wiki/Project_Bento_Testing#Current_Content_.26_Resources)), and the Polygon Object (mesh) **must have zero object transforms or freeze transforms.** In other words, its transformation matrix should be identity, and the polygon object's transform should look like this in C4D's object attribute window:

```
Coordinates
P.X [0 cm] S.X [1] R.H [0 °]
P.Y [0 cm] S.Y [1] R.P [0 °]
P.Z [0 cm] S.Z [1] R.B [0 °]
...
Freeze Transformation
P.X [0 cm] S.X [1] R.H [0 °]
P.Y [0 cm] S.Y [1] R.P [0 °]
P.Z [0 cm] S.Z [1] R.B [0 °]
```

You should export your model using COLLADA 1.4 format. As far as I know, COLLADA 1.5 is not supported.


Running this script on the exported .dae file will create a repaired copy of it that Second Life can read joint weight data from.