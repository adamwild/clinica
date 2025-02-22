# coding: utf8


def init_input_node(t1w, recon_all_args, output_dir):
    """Initialize the pipeline.

    This function will:
        - Extract <image_id> (e.g. sub-CLNC01_ses-M00) T1w filename;
        - Check FOV of T1w;
        - Create SUBJECTS_DIR for recon-all (otherwise, the command won't run);
        - Print begin execution message.
    """
    import os
    import errno
    from clinica.utils.io import get_subject_id
    from clinica.utils.freesurfer import check_flags
    from clinica.utils.ux import print_begin_image

    # Extract <image_id>
    image_id = get_subject_id(t1w)

    # Check flags for T1w
    flags = check_flags(t1w, recon_all_args)

    # Create SUBJECTS_DIR for recon-all (otherwise, the command won't run)
    subjects_dir = os.path.join(output_dir, image_id)
    try:
        os.makedirs(subjects_dir)
    except OSError as e:
        if e.errno != errno.EEXIST:  # EEXIST: folder already exists
            raise e

    print_begin_image(image_id, ['ReconAllArgs'], [flags])

    return image_id, t1w, flags, subjects_dir


def write_tsv_files(subjects_dir, image_id):
    """
    Generate statistics TSV files in `subjects_dir`/regional_measures folder for `image_id`.

    Notes:
        We do not need to check the line "finished without error" in scripts/recon-all.log.
        If an error occurs, it will be detected by Nipype and the next nodes (including
        write_tsv_files will not be called).
    """
    import os
    import datetime
    from colorama import Fore
    from clinica.utils.stream import cprint
    from clinica.utils.freesurfer import generate_regional_measures

    if os.path.isfile(os.path.join(subjects_dir, image_id, 'mri', 'aparc+aseg.mgz')):
        generate_regional_measures(subjects_dir, image_id)
    else:
        now = datetime.datetime.now().strftime('%H:%M:%S')
        cprint('%s[%s] %s does not contain mri/aseg+aparc.mgz file. '
               'Creation of regional_measures/ folder will be skipped.%s' %
               (Fore.YELLOW, now, image_id.replace('_', '|'), Fore.RESET))
    return image_id


def save_to_caps(source_dir, image_id, caps_dir, overwrite_caps=False):
    """Save `source_dir`/`image_id`/ to CAPS folder.

    This function copies outputs of `source_dir`/`image_id`/ to
    `caps_dir`/subjects/<participant_id>/<session_id>/t1_freesurfer_cross_sectional/
    where `image_id` = <participant_id>_<session_id>.

    The `source_dir`/`image_id`/ folder should contain the following elements:
        - fsaverage, lh.EC_average and rh.EC_average symbolic links
        - `image_id`/ folder containing the FreeSurfer segmentation
        - regional_measures/ folder containing TSV files

    Notes:
        We do not need to check the line "finished without error" in scripts/recon-all.log.
        If an error occurs, it will be detected by Nipype and the next nodes (including
        save_to_caps will not be called).

    Raise:
        FileNotFoundError: If symbolic links in `source_dir`/`image_id` folder are not removed
        IOError: If the `source_dir`/`image_id` folder does not contain FreeSurfer segmentation.
    """
    import os
    import datetime
    import errno
    import shutil
    from colorama import Fore
    from clinica.utils.stream import cprint
    from clinica.utils.ux import print_end_image

    participant_id = image_id.split('_')[0]
    session_id = image_id.split('_')[1]

    destination_dir = os.path.join(
        os.path.expanduser(caps_dir),
        'subjects',
        participant_id,
        session_id,
        't1',
        'freesurfer_cross_sectional'
    )

    representative_file = os.path.join(image_id, 'mri', 'aparc+aseg.mgz')
    representative_source_file = os.path.join(os.path.expanduser(source_dir), image_id, representative_file)
    representative_destination_file = os.path.join(destination_dir, representative_file)
    if os.path.isfile(representative_source_file):
        # Remove symbolic links before the copy
        try:
            os.unlink(os.path.join(os.path.expanduser(source_dir), image_id, 'fsaverage'))
            os.unlink(os.path.join(os.path.expanduser(source_dir), image_id, 'lh.EC_average'))
            os.unlink(os.path.join(os.path.expanduser(source_dir), image_id, 'rh.EC_average'))
        except FileNotFoundError as e:
            if e.errno != errno.ENOENT:
                raise e

        if os.path.isfile(representative_destination_file):
            if overwrite_caps:
                raise NotImplementedError('Overwritten of CAPS folder in t1-freesurfer pipeline not implemented')
            else:
                now = datetime.datetime.now().strftime('%H:%M:%S')
                cprint('%s[%s] Previous run of FreeSurfer was found in CAPS folder for %s. '
                       'Copy will be skipped.%s' %
                       (Fore.YELLOW, now, image_id.replace('_', '|'), Fore.RESET))
        else:
            shutil.copytree(os.path.join(source_dir, image_id), destination_dir, symlinks=True)
            print_end_image(image_id)
    else:
        now = datetime.datetime.now().strftime('%H:%M:%S')
        cprint('%s[%s] %s does not contain mri/aseg+aparc.mgz file. '
               'Copy will be skipped.%s' %
               (Fore.YELLOW, now, image_id.replace('_', '|'), Fore.RESET))
    return image_id
