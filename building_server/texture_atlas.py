# -*- coding: utf-8 -*-

from wand.image import Image
from wand.color import Color
import math

# Packing algorithm from http://blackpawn.com/texts/lightmaps/

class Rectangle():
    def __init__(self, left, bottom, width, height):
         self.bottom = bottom
         self.left = left
         self.width = width
         self.height = height


class Node():

    def __init__(self, rectangle):
        self.children = [None, None]
        self.rectangle = rectangle
        self.image = None

    def isLeaf(self):
        return self.children == [None, None]

    def insert(self, texture):
        if not self.isLeaf():
            newNode = self.children[0].insert(texture)
            if newNode is not None:
                return newNode
            return self.children[1].insert(texture)
        else:
            # Node already taken
            if self.image is not None:
                return None

            # Node too small
            if (self.rectangle.width < texture.width or
                self.rectangle.height < texture.height):
                return None

            # Perfect fit
            if (self.rectangle.width == texture.width and
                self.rectangle.height == texture.height):
                return self

            # Fit: split node
            splitSide = (self.rectangle.width - texture.width >
                self.rectangle.height - texture.height)
            if splitSide:
                r1 = Rectangle(self.rectangle.left, self.rectangle.bottom,
                    texture.width, self.rectangle.height)
                r2 = Rectangle(self.rectangle.left + texture.width, self.rectangle.bottom,
                    self.rectangle.width - texture.width, self.rectangle.height)
            else:
                r1 = Rectangle(self.rectangle.left, self.rectangle.bottom,
                    self.rectangle.width, texture.height)
                r2 = Rectangle(self.rectangle.left, self.rectangle.bottom + texture.height,
                    self.rectangle.width, self.rectangle.height - texture.height)

            self.children = [Node(r1), Node(r2)]

            return self.children[0].insert(texture)

class TextureAtlas():

    def __init__(self, rectangle):
        self.root = Node(rectangle)
        self.texture = None
        self.transforms = None
        self.nTextures = 0


    @staticmethod
    def from_texture_array(textures):
        atlas = TextureAtlas(Rectangle(0, 0, 8192, 8192))
        for i, t in enumerate(textures):
            node = atlas.root.insert(t)
            node.image = (i, t)
        atlas.nTextures = len(textures)

        atlas.makeTexture()
        return atlas;

    def makeTexture(self):
        self.texture = Image(width=self.root.rectangle.width, height=self.root.rectangle.height)
        sizes = [None] * self.nTextures
        translations = [None] * self.nTextures
        self.transforms = [None] * self.nTextures

        def walkTree(node):
            if node.image is None:
                if not node.isLeaf():
                    walkTree(node.children[0])
                    walkTree(node.children[1])
                return

            nonlocal sizes, translations
            self.texture.composite(node.image[1], left=node.rectangle.left, top=node.rectangle.bottom)
            translations[node.image[0]] = (node.rectangle.left / node.rectangle.width, node.rectangle.bottom / node.rectangle.height)
            sizes[node.image[0]] = (node.rectangle.width, node.rectangle.height)

        walkTree(self.root)
        self.texture.trim(color=Color('black'))

        for i in range(0, self.nTextures):
            scale = (sizes[i][0] / self.texture.width, sizes[i][1] / self.texture.height)
            self.transforms[i] = (translations[i], scale)

    def getTexture(self):
        return self.texture

    def getTransform(self, i):
        return self.transforms[i]


class Atlas2Atlas:

    def __init__(self):
        self.atlas = None
        self.transforms = []

    @staticmethod
    def from_texture_uv_array(textures, uvs):
        a2a = Atlas2Atlas()

        tex = []
        for t, uv in zip(textures, uvs):
            uv_reshaped = uv.reshape((2,-1), order='F')
            mU, mV = uv_reshaped.min(axis=1)
            MU, MV = uv_reshaped.max(axis=1)
            translation = (mU, mV)
            scale = (1 / (MU - mU), 1 / (MV - mV))
            a2a.transforms.append((translation, scale))

            mX = math.floor(mU * t.width)
            MX = math.ceil(MU * t.width)
            mY = math.floor(mV * t.height)
            MY = math.ceil(MV * t.height)
            tex.append(t[mX:MX, mY:MY])

        a2a.atlas = TextureAtlas.from_texture_array(tex)
        for i in range(0, len(a2a.transforms)):
            atlasTransform = a2a.atlas.getTransform(i)
            translation = (atlasTransform[0][0] + a2a.transforms[i][0][0],
                atlasTransform[0][1] + a2a.transforms[i][0][1])
            scale = (atlasTransform[1][0] * a2a.transforms[i][1][0],
                atlasTransform[1][1] * a2a.transforms[i][1][1])
            a2a.transforms[i] = (translation, scale)

        return a2a

    def getTexture(self):
        return self.atlas.getTexture()

    def transformUV(self, uv, i):
        (translate, scale) = self.transforms[i]
        uv_reshaped = uv.reshape((2,-1), order='F')
        u = uv_reshaped[0]
        v = uv_reshaped[1]
        u += translate[0]
        v += translate[1]
        u *= scale[0]
        v *= scale[1]

    def debug(self):
        self.getTexture().save(filename='test-atlas.png')
        print(self.transforms)



if __name__ == '__main__':
    #img = Image(filename='1')
    #img2 = Image(filename='2')
    img = []
    img.append(Image(width=250, height=120, background=Color('red')))
    img.append(Image(width=200, height=120, background=Color('gray')))
    img.append(Image(width=100, height=200, background=Color('blue')))
    img.append(Image(width=50, height=150, background=Color('green')))
    img.append(Image(width=200, height=120, background=Color('purple')))
    img.append(Image(width=100, height=200, background=Color('yellow')))
    img.append(Image(width=50, height=150, background=Color('pink')))
    img.append(Image(width=100, height=200, background=Color('orange')))

    atlas = TextureAtlas.from_texture_array(img)

    atlas.getTexture().save(filename='test-atlas.png')
