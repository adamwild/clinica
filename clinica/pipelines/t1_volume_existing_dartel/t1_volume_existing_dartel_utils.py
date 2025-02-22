# coding: utf8

import os
from nipype.interfaces.spm.base import SPMCommandInputSpec, SPMCommand, scans_for_fnames
from nipype.interfaces.base import TraitedSpec, File, traits
from nipype.utils.filemanip import split_filename

__author__ = "Jorge Samper-Gonzalez"
__copyright__ = "Copyright 2016-2019 The Aramis Lab Team"
__credits__ = ["Jorge Samper-Gonzalez"]
__license__ = "See LICENSE.txt file"
__version__ = "0.1.0"
__maintainer__ = "Jorge Samper-Gonzalez"
__email__ = "jorge.samper-gonzalez@inria.fr"
__status__ = "Development"


if 'SPMSTANDALONE_HOME' in os.environ:
    if 'MCR_HOME' in os.environ:
        matlab_cmd = os.environ['SPMSTANDALONE_HOME'] \
                + 'run_spm12.sh ' \
                + os.environ['MCR_HOME'] \
                + ' script'
        SPMCommand.set_mlab_paths(matlab_cmd=matlab_cmd, use_mcr=True)


class DARTELExistingTemplateInputSpec(SPMCommandInputSpec):
    image_files = traits.List(traits.List(File(exists=True)),
                              desc="A list of files to be segmented",
                              field='warp1.images', copyfile=False, mandatory=True)
    regularization_form = traits.Enum('Linear', 'Membrane', 'Bending',
                                      field='warp1.settings.rform',
                                      desc='Form of regularization energy term')
    iteration_parameters = traits.List(traits.Tuple(traits.Range(1, 10),
                                                    traits.Tuple(traits.Float,
                                                                 traits.Float,
                                                                 traits.Float),
                                                    traits.Range(0, 9),
                                                    traits.File(exists=True)),
                                       minlen=3,
                                       maxlen=12,
                                       mandatory=True,
                                       field='warp1.settings.param',
                                       desc="""List of tuples for each iteration
                                       - Inner iterations
                                       - Regularization parameters
                                       - Time points for deformation model
                                       - DARTEL template
                                       """)
    optimization_parameters = traits.Tuple(traits.Float, traits.Range(1, 8),
                                           traits.Range(1, 8),
                                           field='warp1.settings.optim',
                                           desc="""Optimization settings a tuple
                                           - LM regularization
                                           - cycles of multigrid solver
                                           - relaxation iterations
                                           """)


class DARTELExistingTemplateOutputSpec(TraitedSpec):
    dartel_flow_fields = traits.List(File(exists=True), desc='DARTEL flow fields')


class DARTELExistingTemplate(SPMCommand):
    """Use SPM DARTEL to create a template and flow fields
    http://www.fil.ion.ucl.ac.uk/spm/doc/manual.pdf#page=185
    Examples
    --------
    >>> import nipype.interfaces.spm as spm
    >>> dartel = spm.DARTEL()
    >>> dartel.inputs.image_files = [['rc1s1.nii','rc1s2.nii'],['rc2s1.nii', 'rc2s2.nii']]
    >>> dartel.run() # doctest: +SKIP
    """

    input_spec = DARTELExistingTemplateInputSpec
    output_spec = DARTELExistingTemplateOutputSpec
    _jobtype = 'tools'
    _jobname = 'dartel'

    def _format_arg(self, opt, spec, val):
        """Convert input to appropriate format for spm
        """
        import numpy as np

        if opt in ['image_files']:
            return scans_for_fnames(val, keep4d=True, separate_sessions=True)
        elif opt == 'regularization_form':
            mapper = {'Linear': 0, 'Membrane': 1, 'Bending': 2}
            return mapper[val]
        elif opt == 'iteration_parameters':
            params = []
            for param in val:
                new_param = {}
                new_param['its'] = param[0]
                new_param['rparam'] = list(param[1])
                new_param['K'] = param[2]
                new_param['template'] = np.array([param[3]], dtype=object)
                params.append(new_param)
            return params
        elif opt == 'optimization_parameters':
            new_param = {}
            new_param['lmreg'] = val[0]
            new_param['cyc'] = val[1]
            new_param['its'] = val[2]
            return [new_param]
        else:
            return super(DARTELExistingTemplate, self)._format_arg(opt, spec, val)

    def _list_outputs(self):
        outputs = self._outputs().get()
        outputs['dartel_flow_fields'] = []
        for filename in self.inputs.image_files[0]:
            pth, base, ext = split_filename(filename)
            outputs['dartel_flow_fields'].append(os.path.realpath('u_%s%s' % (base, ext)))
        return outputs


def prepare_dartel_input_images(dartel_input_images):
    return [[[tissue] for tissue in subject] for subject in zip(*dartel_input_images)]


def prepare_images_from_segmentation(dartel_input_images):
    return [[tissue for tissue in subject if tissue] for subject in dartel_input_images if subject]


def create_iteration_parameters(dartel_templates, iteration_parameters):

    if len(dartel_templates) != 6:
        raise ValueError('Wrong number of templates. 6 templates were expected, one for each DARTEL iteration.')

    if iteration_parameters is None:
        iter1 = (3, (4, 2, 1e-06), 0, dartel_templates[0])
        iter2 = (3, (2, 1, 1e-06), 0, dartel_templates[1])
        iter3 = (3, (1, 0.5, 1e-06), 1, dartel_templates[2])
        iter4 = (3, (0.5, 0.25, 1e-06), 2, dartel_templates[3])
        iter5 = (3, (0.25, 0.125, 1e-06), 4, dartel_templates[4])
        iter6 = (3, (0.25, 0.125, 1e-06), 6, dartel_templates[5])

        return [iter1, iter2, iter3, iter4, iter5, iter6]

    elif len(iteration_parameters) != 6:
        raise ValueError('Wrong number of iteration parameters. 6 iterations were expected.')
    else:
        new_iteration_parameters = []
        for i in range(6):
            new_iteration_parameters.append((iteration_parameters[i][0],
                                             iteration_parameters[i][1],
                                             iteration_parameters[i][2],
                                             dartel_templates[i])
                                            )
        return new_iteration_parameters


def get_class_images(class_images, index_list):
    """
    Utility method to extract class images from a multi session <class_images> set.

    Tissue types are:
        - 1: Grey Matter
        - 2: White Matter
        - 3: CerebroSpinal Fluid
        - 4: Skull
        - 5: Out-of-brain soft tissue
        - 6: Head surrounding

    Args:
        class_images: image set from which to extract images.
        index_list: index list of the classes to extract.

    Returns:
        Extracted images in a list of lists (without empty lists).

    Example:
    >>> class_n_images = get_class_images(class_images,[1,2])
    """
    # Declare class images list
    class_n_images = {}
    for idx in index_list:
        class_n_images[idx] = []

    for session in class_images:
        for idx in index_list:
            class_n_images[idx].extend(session[idx-1])

    result = []
    for idx in index_list:
        if class_n_images[idx]:
            result.append([class_n_images[idx]])

    return result
