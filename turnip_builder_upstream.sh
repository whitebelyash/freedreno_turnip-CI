#!/bin/bash -e

#Define variables
green='\033[0;32m'
red='\033[0;31m'
nocolor='\033[0m'
deps="git meson ninja patchelf unzip curl pip flex bison zip glslang glslangValidator"
scriptdir="$(cd "$(dirname "$0")" && pwd)"
workdir="$(pwd)/turnip_workdir"
magiskdir="$workdir/turnip_module"
ndkver="android-ndk-r29"
ndk="$workdir/$ndkver/toolchains/llvm/prebuilt/linux-x86_64/bin"
sdkver="34"
mesasrc="https://gitlab.freedesktop.org/mesa/mesa.git"
srcfolder="mesa"

# Optional: pin to a specific commit (set via env or leave empty for latest)
MESA_COMMIT="${MESA_COMMIT:-}"

clear

#There are 4 functions here, simply comment to disable.
#You can insert your own function and make a pull request.
run_all(){
	echo "====== Begin building TU V$BUILD_VERSION! ======"
	check_deps
	prepare_workdir
	build_lib_for_android main tu8_kgsl.patch
}

check_deps(){
	echo "Checking system for required Dependencies ..."
		for deps_chk in $deps;
			do
				sleep 0.25
				if command -v "$deps_chk" >/dev/null 2>&1 ; then
					echo -e "$green - $deps_chk found $nocolor"
				else
					echo -e "$red - $deps_chk not found, can't countinue. $nocolor"
					deps_missing=1
				fi;
			done

		if [ "$deps_missing" == "1" ]
			then echo "Please install missing dependencies" && exit 1
		fi

	echo "Installing python Mako dependency (if missing) ..." $'\n'
		pip install mako &> /dev/null
}

prepare_workdir(){
	echo "Preparing work directory ..." $'\n'
		mkdir -p "$workdir" && cd "$_"

	echo "Downloading android-ndk from google server ..." $'\n'
		curl https://dl.google.com/android/repository/"$ndkver"-linux.zip --output "$ndkver"-linux.zip &> /dev/null
	echo "Exracting android-ndk ..." $'\n'
		unzip "$ndkver"-linux.zip &> /dev/null

	if [ -n "$MESA_COMMIT" ]; then
		echo "Downloading mesa source (commit $MESA_COMMIT) ..." $'\n'
		curl -L "https://gitlab.freedesktop.org/mesa/mesa/-/archive/$MESA_COMMIT/mesa-$MESA_COMMIT.tar.gz" -o mesa.tar.gz
		tar xzf mesa.tar.gz
		mv mesa-$MESA_COMMIT* $srcfolder
		cd $srcfolder
		git init && git add -A && git commit -q -m "mesa $MESA_COMMIT"
	else
		echo "Cloning latest mesa source (main branch) ..." $'\n'
		git clone --depth=1 --branch main "$mesasrc" "$srcfolder"
		cd $srcfolder
	fi
}


apply_timeline_sync_fix(){
	local kgsl_file="src/freedreno/vulkan/tu_knl_kgsl.cc"
	if ! grep -q "vk_kgsl_timeline_type" "$kgsl_file" 2>/dev/null; then
		echo "Timeline sync not present in patchset, skipping fix"
		return
	fi

	python3 "$scriptdir/patches/fix_timeline_sync.py" "$kgsl_file"

	if grep -q "kgsl_binary_timeline_import_sync_file" "$kgsl_file"; then
		echo -e "${green}Timeline sync Android fix applied successfully${nocolor}"
	else
		echo -e "${red}Warning: Timeline sync fix failed to apply${nocolor}"
		exit 1
	fi
}

apply_devices_fix(){
	local devices_file="src/freedreno/common/freedreno_devices.py"
	if [ ! -f "$devices_file" ]; then
		echo -e "${red}freedreno_devices.py not found!${nocolor}"
		exit 1
	fi

	python3 "$scriptdir/patches/fix_devices.py" "$devices_file"

	if grep -q "a8xx_825" "$devices_file"; then
		echo -e "${green}Device entries fix applied successfully${nocolor}"
	else
		echo -e "${red}Warning: Device entries fix failed to apply${nocolor}"
		exit 1
	fi
}

build_lib_for_android(){
	echo "==== Building Mesa on $1 branch ===="
	#git reset --hard
	echo "Downloading patch... ($2)"
    	wget https://github.com/whitebelyash/mesa-tu8/releases/download/patchset-head-v2/$2

	echo "Filtering freedreno_devices.py hunks from patch..."
	python3 "$scriptdir/patches/filter_patch.py" "$2" "${2%.patch}_filtered.patch"

	echo "Applying filtered patches..."
		if ! git apply "${2%.patch}_filtered.patch"; then
			echo "git apply failed, trying git am..."
			git am --abort 2>/dev/null || true
			if ! git am --3way "${2%.patch}_filtered.patch"; then
				echo "Failed to apply ${2%.patch}_filtered.patch!"
				exit 1
			fi
		fi

	echo "Applying freedreno_devices.py fixes..."
	apply_devices_fix

	echo "Applying timeline sync Android fix..."
	apply_timeline_sync_fix
	#git checkout origin/$1
	#Workaround for using Clang as c compiler instead of GCC
	mkdir -p "$workdir/bin"
	ln -sf "$ndk/clang" "$workdir/bin/cc"
	ln -sf "$ndk/clang++" "$workdir/bin/c++"
	export PATH="$workdir/bin:$ndk:$PATH"
	export CC=clang
	export CXX=clang++
	export AR=llvm-ar
	export RANLIB=llvm-ranlib
	export STRIP=llvm-strip
	export OBJDUMP=llvm-objdump
	export OBJCOPY=llvm-objcopy
	export LDFLAGS="-fuse-ld=lld"
	GITHASH=$(git rev-parse --short HEAD)

	echo "Generating build files ..." $'\n'
		cat <<EOF >"android-aarch64.txt"
[binaries]
ar = '$ndk/llvm-ar'
c = ['ccache', '$ndk/aarch64-linux-android$sdkver-clang']
cpp = ['ccache', '$ndk/aarch64-linux-android$sdkver-clang++', '-fno-exceptions', '-fno-unwind-tables', '-fno-asynchronous-unwind-tables', '--start-no-unused-arguments', '-static-libstdc++', '--end-no-unused-arguments']
c_ld = '$ndk/ld.lld'
cpp_ld = '$ndk/ld.lld'
strip = '$ndk/llvm-strip'
pkg-config = ['env', 'PKG_CONFIG_LIBDIR=$ndk/pkg-config', '/usr/bin/pkg-config']

[host_machine]
system = 'android'
cpu_family = 'aarch64'
cpu = 'armv8'
endian = 'little'
EOF

		cat <<EOF >"native.txt"
[build_machine]
c = ['ccache', 'clang']
cpp = ['ccache', 'clang++']
ar = 'llvm-ar'
strip = 'llvm-strip'
c_ld = 'ld.lld'
cpp_ld = 'ld.lld'
system = 'linux'
cpu_family = 'x86_64'
cpu = 'x86_64'
endian = 'little'
EOF

		meson setup build-android-aarch64 \
			--cross-file "android-aarch64.txt" \
			--native-file "native.txt" \
			--prefix /tmp/turnip-$1 \
			-Dbuildtype=release \
			-Dstrip=true \
			-Dplatforms=android \
			-Dvideo-codecs= \
			-Dplatform-sdk-version="$sdkver" \
			-Dandroid-stub=true \
			-Dgallium-drivers= \
			-Dvulkan-drivers=freedreno \
			-Dvulkan-beta=true \
			-Dfreedreno-kmds=kgsl \
			-Degl=disabled \
			-Dplatform-sdk-version=36 \
			-Dandroid-libbacktrace=disabled \
			--reconfigure

	echo "Compiling build files ..." $'\n'
		ninja -C build-android-aarch64 install

	if ! [ -a /tmp/turnip-$1/lib/libvulkan_freedreno.so ]; then
		echo -e "$red Build failed! $nocolor" && exit 1
	fi
	echo "Making the archive"
	cd /tmp/turnip-$1/lib
	cat <<EOF >"meta.json"
{
  "schemaVersion": 1,
  "name": "Mesa Turnip v$BUILD_VERSION-$GITHASH",
  "description": "Mesa-git Freedreno/Turnip adapted for AdrenoTools (git $GITHASH)",
  "author": "whitebelyash",
  "packageVersion": "1",
  "vendor": "Mesa",
  "driverVersion": "Vulkan 1.4.335",
  "minApi": 28,
  "libraryName": "libvulkan_freedreno.so"
}
EOF
zip /tmp/mesa-turnip-$1-V$BUILD_VERSION.zip libvulkan_freedreno.so meta.json
cd -
if ! [ -a /tmp/mesa-turnip-$1-V$BUILD_VERSION.zip ]; then
	echo -e "$red Failed to pack the archive! $nocolor"
fi
}

run_all
