<?php

// autoload_static.php @generated by Composer

namespace Composer\Autoload;

class ComposerStaticInit414d903ce05efdcbe48414c1bc4a211b
{
    public static $prefixLengthsPsr4 = array (
        'P' => 
        array (
            'PHPMailer\\PHPMailer\\' => 20,
        ),
    );

    public static $prefixDirsPsr4 = array (
        'PHPMailer\\PHPMailer\\' => 
        array (
            0 => __DIR__ . '/..' . '/phpmailer/phpmailer/src',
        ),
    );

    public static $classMap = array (
        'Composer\\InstalledVersions' => __DIR__ . '/..' . '/composer/InstalledVersions.php',
    );

    public static function getInitializer(ClassLoader $loader)
    {
        return \Closure::bind(function () use ($loader) {
            $loader->prefixLengthsPsr4 = ComposerStaticInit414d903ce05efdcbe48414c1bc4a211b::$prefixLengthsPsr4;
            $loader->prefixDirsPsr4 = ComposerStaticInit414d903ce05efdcbe48414c1bc4a211b::$prefixDirsPsr4;
            $loader->classMap = ComposerStaticInit414d903ce05efdcbe48414c1bc4a211b::$classMap;

        }, null, ClassLoader::class);
    }
}
